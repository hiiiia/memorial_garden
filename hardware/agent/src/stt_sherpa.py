from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import wave
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


ENGINE_NAME = "sherpa-onnx-korean-zipformer-int8"
MODEL_DIR_NAME = "sherpa-onnx-zipformer-korean-2024-06-24"
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_FEATURE_DIM = 80
DEFAULT_DECODING_METHOD = "greedy_search"
MIN_WAV_BYTES = 1024


class SherpaSttError(RuntimeError):
    def __init__(self, message: str, code: str = "SHERPA_STT_ERROR") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SherpaModelFiles:
    encoder: Path
    decoder: Path
    joiner: Path
    tokens: Path


@dataclass(frozen=True)
class SherpaConfig:
    model_dir: Path
    num_threads: int
    sample_rate: int = DEFAULT_SAMPLE_RATE
    feature_dim: int = DEFAULT_FEATURE_DIM
    decoding_method: str = DEFAULT_DECODING_METHOD


@dataclass(frozen=True)
class WavInfo:
    path: Path
    size_bytes: int
    sample_rate: int
    channels: int
    sample_width_bytes: int
    frames: int
    duration_seconds: float

    @property
    def sample_width_bits(self) -> int:
        return self.sample_width_bytes * 8


@dataclass(frozen=True)
class SherpaSttResult:
    text: str
    wav_info: WavInfo
    inference_seconds: float
    rtf: float
    model_loaded_now: bool


def _repo_hardware_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def default_model_dir() -> Path:
    return _repo_hardware_dir() / "models" / MODEL_DIR_NAME


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        print(f"[STT] {name} 값이 정수가 아니어서 기본값 {default}을 사용합니다.")
        return default
    if value < minimum:
        print(f"[STT] {name} 값이 너무 작아서 기본값 {default}을 사용합니다.")
        return default
    return value


def _default_num_threads() -> int:
    return max(1, min(4, os.cpu_count() or 1))


def config_from_env() -> SherpaConfig:
    model_dir = Path(os.getenv("SHERPA_MODEL_DIR", str(default_model_dir()))).expanduser()
    threads = _env_int("SHERPA_NUM_THREADS", _default_num_threads())
    config = SherpaConfig(model_dir=model_dir, num_threads=threads)
    print(
        f"[STT] engine={ENGINE_NAME}, model_dir={config.model_dir}, "
        f"num_threads={config.num_threads}"
    )
    return config


def _find_one(model_dir: Path, pattern: str, label: str) -> Path:
    matches = sorted(model_dir.glob(pattern))
    if not matches:
        raise SherpaSttError(
            (
                f"{label} 모델 파일을 찾지 못했습니다: {model_dir}/{pattern}\n"
                f"모델을 내려받은 뒤 SHERPA_MODEL_DIR를 확인하세요. "
                f"예: hardware/models/{MODEL_DIR_NAME}"
            ),
            code="MISSING_MODEL_FILE",
        )
    if len(matches) > 1:
        print(f"[STT] {label} 후보가 여러 개라 첫 번째 파일을 사용합니다: {matches[0]}")
    return matches[0]


def resolve_model_files(model_dir: Path) -> SherpaModelFiles:
    if not model_dir.exists() or not model_dir.is_dir():
        raise SherpaSttError(
            (
                f"Sherpa 모델 디렉터리가 없습니다: {model_dir}\n"
                "설치 방법: hardware/README_SHERPA_STT.md의 모델 다운로드 절차를 실행하세요."
            ),
            code="MISSING_MODEL_DIR",
        )

    return SherpaModelFiles(
        encoder=_find_one(model_dir, "encoder*int8*.onnx", "encoder int8"),
        decoder=_find_one(model_dir, "decoder*int8*.onnx", "decoder int8"),
        joiner=_find_one(model_dir, "joiner*int8*.onnx", "joiner int8"),
        tokens=_find_one(model_dir, "tokens.txt", "tokens"),
    )


def inspect_wav(wav_path: str | Path) -> WavInfo:
    path = Path(wav_path)
    if not path.exists():
        raise SherpaSttError(f"WAV 파일이 없습니다: {path}", code="WAV_NOT_FOUND")
    if not path.is_file():
        raise SherpaSttError(f"WAV 경로가 파일이 아닙니다: {path}", code="WAV_NOT_FILE")

    size_bytes = path.stat().st_size
    if size_bytes < MIN_WAV_BYTES:
        raise SherpaSttError(f"WAV 파일이 너무 작습니다: {size_bytes} bytes", code="WAV_TOO_SMALL")

    try:
        with wave.open(str(path), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_width_bytes = wav_file.getsampwidth()
            sample_rate = wav_file.getframerate()
            frames = wav_file.getnframes()
            compression = wav_file.getcomptype()
    except wave.Error as exc:
        raise SherpaSttError(f"PCM WAV 파일을 읽지 못했습니다: {exc}", code="INVALID_WAV") from exc

    if compression != "NONE":
        raise SherpaSttError(f"압축 WAV는 지원하지 않습니다: {compression}", code="UNSUPPORTED_WAV")
    if channels != 1:
        raise SherpaSttError(f"Sherpa 입력은 mono WAV만 지원합니다: channels={channels}", code="UNSUPPORTED_CHANNELS")
    if sample_width_bytes != 2:
        raise SherpaSttError(
            f"Sherpa 입력은 16-bit PCM WAV만 지원합니다: width={sample_width_bytes * 8}bit",
            code="UNSUPPORTED_SAMPLE_WIDTH",
        )
    if sample_rate <= 0:
        raise SherpaSttError(f"WAV sample rate가 올바르지 않습니다: {sample_rate}", code="INVALID_SAMPLE_RATE")

    duration_seconds = frames / float(sample_rate)
    if duration_seconds <= 0.2:
        raise SherpaSttError(f"WAV 길이가 너무 짧습니다: {duration_seconds:.2f}s", code="WAV_TOO_SHORT")

    return WavInfo(
        path=path,
        size_bytes=size_bytes,
        sample_rate=sample_rate,
        channels=channels,
        sample_width_bytes=sample_width_bytes,
        frames=frames,
        duration_seconds=duration_seconds,
    )


def _read_wave_samples(wav_info: WavInfo):
    try:
        import numpy as np
    except ImportError as exc:
        raise SherpaSttError("numpy 패키지가 설치되어 있지 않습니다.", code="MISSING_NUMPY") from exc

    with wave.open(str(wav_info.path), "rb") as wav_file:
        samples = wav_file.readframes(wav_info.frames)

    samples_int16 = np.frombuffer(samples, dtype=np.int16)
    return samples_int16.astype(np.float32) / 32768.0


class SherpaOnnxKoreanTranscriber:
    def __init__(self, config: Optional[SherpaConfig] = None) -> None:
        self.config = config or config_from_env()
        self._recognizer = None
        self._model_files: Optional[SherpaModelFiles] = None
        self._lock = threading.Lock()

    @classmethod
    def from_env(cls) -> "SherpaOnnxKoreanTranscriber":
        return cls(config_from_env())

    def _load_recognizer_locked(self):
        if self._recognizer is not None:
            return self._recognizer, False

        try:
            import sherpa_onnx
        except ImportError as exc:
            raise SherpaSttError(
                "sherpa-onnx 패키지가 설치되어 있지 않습니다. "
                "hardware/agent/requirements.txt 설치를 확인하세요.",
                code="MISSING_SHERPA_ONNX",
            ) from exc

        self._model_files = resolve_model_files(self.config.model_dir)
        print(f"[STT] Sherpa 모델 최초 로딩: {self.config.model_dir}")
        print(f"[STT] encoder={self._model_files.encoder}")
        print(f"[STT] decoder={self._model_files.decoder}")
        print(f"[STT] joiner={self._model_files.joiner}")
        print(f"[STT] tokens={self._model_files.tokens}")

        self._recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(self._model_files.encoder),
            decoder=str(self._model_files.decoder),
            joiner=str(self._model_files.joiner),
            tokens=str(self._model_files.tokens),
            num_threads=self.config.num_threads,
            sample_rate=self.config.sample_rate,
            feature_dim=self.config.feature_dim,
            decoding_method=self.config.decoding_method,
            debug=False,
        )
        return self._recognizer, True

    def _get_recognizer(self):
        with self._lock:
            return self._load_recognizer_locked()

    def transcribe(self, wav_path: str | Path) -> SherpaSttResult:
        wav_info = inspect_wav(wav_path)
        print(f"[STT] engine={ENGINE_NAME}")
        print(
            "[STT] "
            f"audio={wav_info.duration_seconds:.2f}s, "
            f"sample_rate={wav_info.sample_rate}, "
            f"channels={wav_info.channels}, "
            f"width={wav_info.sample_width_bits}bit"
        )
        if wav_info.sample_rate != self.config.sample_rate:
            print(
                f"[STT] 입력 sample_rate={wav_info.sample_rate}Hz, "
                f"feature sample_rate={self.config.sample_rate}Hz. Sherpa가 내부 resample을 수행합니다."
            )

        recognizer, model_loaded_now = self._get_recognizer()
        print(f"[STT] model={'loaded' if model_loaded_now else 'reused'}")

        samples = _read_wave_samples(wav_info)
        stream = recognizer.create_stream()
        stream.accept_waveform(wav_info.sample_rate, samples)

        started_at = time.perf_counter()
        recognizer.decode_streams([stream])
        inference_seconds = time.perf_counter() - started_at
        rtf = inference_seconds / wav_info.duration_seconds

        text = (stream.result.text or "").strip()
        print(f"[STT] inference={inference_seconds:.2f}s, rtf={rtf:.3f}")
        print(f"[STT] text={text}")

        if not text:
            raise SherpaSttError("STT 결과가 비어 있습니다.", code="EMPTY_TRANSCRIPT")

        return SherpaSttResult(
            text=text,
            wav_info=wav_info,
            inference_seconds=inference_seconds,
            rtf=rtf,
            model_loaded_now=model_loaded_now,
        )


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Sherpa-ONNX Korean Zipformer int8 WAV STT 테스트")
    parser.add_argument("--file", required=True, help="STT 처리할 mono 16-bit PCM WAV 파일 경로")
    args = parser.parse_args()

    started_at = datetime.now()
    print(f"[STT CLI] WAV 파일: {args.file}")
    print(f"[STT CLI] 시작 시각: {started_at.isoformat(timespec='seconds')}")

    try:
        wav_info = inspect_wav(args.file)
        print(f"[STT CLI] 파일 크기: {wav_info.size_bytes} bytes")
        print(
            "[STT CLI] WAV 정보: "
            f"{wav_info.duration_seconds:.2f}s, "
            f"{wav_info.sample_rate}Hz, "
            f"{wav_info.channels}ch, "
            f"{wav_info.sample_width_bits}bit"
        )
        result = SherpaOnnxKoreanTranscriber.from_env().transcribe(args.file)
        finished_at = datetime.now()
        print(f"[STT CLI] 종료 시각: {finished_at.isoformat(timespec='seconds')}")
        print(f"[STT CLI] 추론 시간: {result.inference_seconds:.2f}s")
        print(f"[STT CLI] RTF: {result.rtf:.3f}")
        print(f"[STT CLI] 인식 텍스트: {result.text}")
        return 0
    except SherpaSttError as exc:
        finished_at = datetime.now()
        print(f"[STT CLI] 종료 시각: {finished_at.isoformat(timespec='seconds')}")
        print(f"[STT CLI] 오류({exc.code}): {exc}", file=sys.stderr)
        return 2


def main() -> int:
    return _cli()


if __name__ == "__main__":
    raise SystemExit(main())
