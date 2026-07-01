from __future__ import annotations

import argparse
import os
import re
import subprocess
import time
import wave
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


DEFAULT_WHISPER_CPP_BIN = "/home/pi/whisper.cpp/build/bin/whisper-cli"
DEFAULT_WHISPER_MODEL_PATH = "/home/pi/whisper.cpp/models/ggml-base.bin"
DEFAULT_LANGUAGE = "ko"
DEFAULT_THREADS = 3
DEFAULT_NICE = 10
DEFAULT_TIMEOUT_SECONDS = 180
MIN_WAV_BYTES = 1024
MIN_DURATION_SECONDS = 0.2


class WhisperCppError(RuntimeError):
    def __init__(self, message: str, code: str = "WHISPER_CPP_ERROR") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class WhisperCppConfig:
    binary_path: Path
    model_path: Path
    language: str
    threads: int
    nice: int
    timeout_seconds: int


@dataclass(frozen=True)
class WavInfo:
    path: Path
    size_bytes: int
    channels: int
    sample_rate: int
    sample_width_bytes: int
    frame_count: int
    duration_seconds: float
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class WhisperCppResult:
    wav_path: Path
    text: str
    elapsed_seconds: float
    wav_info: WavInfo
    command: tuple[str, ...]


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        print(f"[Whisper.cpp] {name} 값이 정수가 아니어서 기본값 {default}을 사용합니다.")
        return default
    return max(minimum, value)


def config_from_env() -> WhisperCppConfig:
    return WhisperCppConfig(
        binary_path=Path(os.getenv("WHISPER_CPP_BIN", DEFAULT_WHISPER_CPP_BIN)).expanduser(),
        model_path=Path(os.getenv("WHISPER_MODEL_PATH", DEFAULT_WHISPER_MODEL_PATH)).expanduser(),
        language=os.getenv("WHISPER_LANGUAGE", DEFAULT_LANGUAGE).strip() or DEFAULT_LANGUAGE,
        threads=_env_int("WHISPER_THREADS", DEFAULT_THREADS),
        nice=_env_int("WHISPER_NICE", DEFAULT_NICE, minimum=0),
        timeout_seconds=_env_int("WHISPER_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS),
    )


def inspect_wav(file_path: str | Path) -> WavInfo:
    path = Path(file_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise WhisperCppError(f"WAV 파일이 없습니다: {path}", code="WAV_NOT_FOUND")

    size_bytes = path.stat().st_size
    if size_bytes < MIN_WAV_BYTES:
        raise WhisperCppError(f"WAV 파일이 너무 작습니다: {size_bytes} bytes", code="WAV_TOO_SMALL")

    try:
        with wave.open(str(path), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_rate = wav_file.getframerate()
            sample_width_bytes = wav_file.getsampwidth()
            frame_count = wav_file.getnframes()
            compression = wav_file.getcomptype()
    except wave.Error as exc:
        raise WhisperCppError(f"PCM WAV 파일을 읽지 못했습니다: {exc}", code="INVALID_WAV") from exc

    if compression != "NONE":
        raise WhisperCppError(f"압축 WAV는 지원하지 않습니다: {compression}", code="UNSUPPORTED_WAV")

    duration_seconds = frame_count / sample_rate if sample_rate else 0.0
    if duration_seconds < MIN_DURATION_SECONDS:
        raise WhisperCppError(
            f"WAV 길이가 너무 짧습니다: {duration_seconds:.2f}s",
            code="WAV_TOO_SHORT",
        )

    warnings: list[str] = []
    if channels != 1:
        warnings.append(f"mono 권장: 현재 channels={channels}")
    if sample_rate != 16000:
        warnings.append(f"16kHz 권장: 현재 sample_rate={sample_rate}")
    if sample_width_bytes != 2:
        warnings.append(f"16-bit PCM 권장: 현재 sample_width={sample_width_bytes * 8}-bit")

    return WavInfo(
        path=path,
        size_bytes=size_bytes,
        channels=channels,
        sample_rate=sample_rate,
        sample_width_bytes=sample_width_bytes,
        frame_count=frame_count,
        duration_seconds=duration_seconds,
        warnings=tuple(warnings),
    )


def _validate_config(config: WhisperCppConfig) -> None:
    if not config.binary_path.exists() or not config.binary_path.is_file():
        raise WhisperCppError(f"whisper-cli 실행 파일이 없습니다: {config.binary_path}", code="MISSING_BINARY")
    if not config.model_path.exists() or not config.model_path.is_file():
        raise WhisperCppError(f"Whisper 모델 파일이 없습니다: {config.model_path}", code="MISSING_MODEL")
    if "base.en" in config.model_path.name.lower():
        raise WhisperCppError("한국어 STT에는 base.en 모델을 사용할 수 없습니다. ggml-base.bin을 사용하세요.", code="ENGLISH_ONLY_MODEL")
    if not os.access(config.binary_path, os.X_OK):
        raise WhisperCppError(f"whisper-cli 실행 권한이 없습니다: {config.binary_path}", code="BINARY_NOT_EXECUTABLE")


def build_whisper_command(config: WhisperCppConfig, wav_path: str | Path) -> list[str]:
    command = [
        str(config.binary_path),
        "-m",
        str(config.model_path),
        "-f",
        str(Path(wav_path)),
        "-l",
        config.language,
        "-t",
        str(config.threads),
        "-nt",
    ]
    if config.nice > 0:
        return ["nice", "-n", str(config.nice), *command]
    return command


_TIMESTAMP_PREFIX = re.compile(r"^\s*\[[^\]]+\]\s*")
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def clean_transcript(raw_output: str) -> str:
    lines: list[str] = []
    for raw_line in raw_output.splitlines():
        line = _ANSI_ESCAPE.sub("", raw_line).strip()
        if not line:
            continue
        lower = line.casefold()
        if lower.startswith(("whisper_", "main:", "ggml_", "system_info:", "sampling:")):
            continue
        if "whisper_print_timings" in lower or "load time" in lower or "total time" in lower:
            continue
        line = _TIMESTAMP_PREFIX.sub("", line).strip()
        if line:
            lines.append(line)
    return " ".join(lines).strip()


class WhisperCppTranscriber:
    def __init__(self, config: Optional[WhisperCppConfig] = None) -> None:
        self.config = config or config_from_env()

    @classmethod
    def from_env(cls) -> "WhisperCppTranscriber":
        return cls(config_from_env())

    def transcribe(self, wav_path: str | Path) -> WhisperCppResult:
        started = time.monotonic()
        _validate_config(self.config)
        wav_info = inspect_wav(wav_path)
        for warning in wav_info.warnings:
            print(f"[Whisper.cpp] WAV 형식 경고: {warning}")

        command = build_whisper_command(self.config, wav_info.path)
        print(f"[Whisper.cpp] STT 시작: {' '.join(command[:-1])} <wav>")

        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds,
                shell=False,
            )
        except FileNotFoundError as exc:
            raise WhisperCppError(f"실행 파일을 찾지 못했습니다: {exc}", code="COMMAND_NOT_FOUND") from exc
        except subprocess.TimeoutExpired as exc:
            raise WhisperCppError(f"STT 처리 시간이 초과되었습니다: {self.config.timeout_seconds}s", code="TIMEOUT") from exc

        elapsed = time.monotonic() - started
        if completed.returncode != 0:
            error_text = (completed.stderr or completed.stdout or "").strip()
            raise WhisperCppError(
                f"whisper.cpp 실행 실패(returncode={completed.returncode}): {error_text[:500]}",
                code="PROCESS_FAILED",
            )

        text = clean_transcript(completed.stdout) or clean_transcript(completed.stderr)
        if not text:
            raise WhisperCppError("STT 결과가 비어 있습니다.", code="EMPTY_TRANSCRIPT")

        print(f"[Whisper.cpp] STT 완료 ({elapsed:.2f}s): {text[:80]}")
        return WhisperCppResult(
            wav_path=wav_info.path,
            text=text,
            elapsed_seconds=elapsed,
            wav_info=wav_info,
            command=tuple(command),
        )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="whisper.cpp 기반 로컬 WAV STT 테스트")
    parser.add_argument("--file", required=True, help="테스트할 WAV 파일 경로")
    args = parser.parse_args(argv)

    started_at = datetime.now()
    print(f"[Whisper.cpp CLI] WAV 파일: {args.file}")
    print(f"[Whisper.cpp CLI] 시작 시각: {started_at.isoformat(timespec='seconds')}")

    try:
        info = inspect_wav(args.file)
        print(f"[Whisper.cpp CLI] 파일 크기: {info.size_bytes} bytes")
        print(
            "[Whisper.cpp CLI] WAV 정보: "
            f"channels={info.channels}, sample_rate={info.sample_rate}, "
            f"sample_width={info.sample_width_bytes * 8}-bit, duration={info.duration_seconds:.2f}s"
        )
        for warning in info.warnings:
            print(f"[Whisper.cpp CLI] WAV 형식 경고: {warning}")

        result = WhisperCppTranscriber.from_env().transcribe(args.file)
        finished_at = datetime.now()
        print(f"[Whisper.cpp CLI] 종료 시각: {finished_at.isoformat(timespec='seconds')}")
        print(f"[Whisper.cpp CLI] 총 처리 시간: {result.elapsed_seconds:.2f}s")
        print(f"[Whisper.cpp CLI] 인식 텍스트: {result.text}")
        return 0
    except WhisperCppError as exc:
        finished_at = datetime.now()
        print(f"[Whisper.cpp CLI] 종료 시각: {finished_at.isoformat(timespec='seconds')}")
        print(f"[Whisper.cpp CLI] 오류({exc.code}): {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
