from __future__ import annotations

import logging
import os
import re
import shlex
import shutil
import signal
import subprocess
import threading
import time
import uuid
import wave
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Literal, Optional, Sequence


logger = logging.getLogger(__name__)

HardwareState = Literal["idle", "recording", "playing", "error"]
DEFAULT_CARD_MATCH = "Google voiceHAT Soundcard"


class AudioControllerError(RuntimeError):
    """하드웨어 오디오 제어 오류의 기본 예외입니다."""


class AudioUnavailableError(AudioControllerError):
    """ALSA 장치나 실행 파일을 사용할 수 없을 때 발생합니다."""


class AudioConflictError(AudioControllerError):
    """현재 상태와 충돌하는 녹음/재생 요청일 때 발생합니다."""


class AudioPathNotAllowedError(AudioControllerError):
    """허용된 오디오 폴더 밖의 파일을 요청했을 때 발생합니다."""


class AudioFileNotFoundError(AudioControllerError):
    """요청한 오디오 파일이 없을 때 발생합니다."""


class InvalidRecordingError(AudioControllerError):
    """녹음 결과가 비어 있거나 정상 WAV가 아닐 때 발생합니다."""


@dataclass(frozen=True)
class AlsaDeviceInfo:
    device: str
    source: str
    card_index: Optional[int] = None
    card_name: Optional[str] = None


@dataclass(frozen=True)
class RecordingResult:
    file_path: str
    size_bytes: int
    duration_seconds: float


def _normalize_card_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _format_command(command: Sequence[str]) -> str:
    return shlex.join(str(part) for part in command)


def find_matching_alsa_card(text: str, card_match: str) -> Optional[tuple[int, str]]:
    """`/proc/asound/cards`, `arecord -l`, `aplay -l` 출력에서 카드 번호를 찾습니다."""
    normalized_match = _normalize_card_text(card_match)
    match_tokens = [normalized_match]
    if normalized_match.startswith("googlevoicehat"):
        match_tokens.append("googlevoicehat")

    lines = text.splitlines()
    proc_header = re.compile(
        r"^\s*(?P<index>\d+)\s+\[(?P<short>[^\]]+)\]\s*:\s*(?P<label>.+)$"
    )
    alsa_list_header = re.compile(
        r"card\s+(?P<index>\d+)\s*:\s*(?P<short>[^\[]*)\[(?P<label>[^\]]+)\]",
        re.IGNORECASE,
    )

    for index, line in enumerate(lines):
        header = proc_header.search(line) or alsa_list_header.search(line)
        if not header:
            continue

        block_lines = [line]
        for following_line in lines[index + 1 :]:
            if proc_header.search(following_line) or alsa_list_header.search(following_line):
                break
            block_lines.append(following_line)
        block = " ".join(block_lines)
        normalized_block = _normalize_card_text(block)
        if any(token and token in normalized_block for token in match_tokens):
            card_name = header.group("label").strip()
            return int(header.group("index")), card_name

    return None


class AlsaDeviceResolver:
    """환경변수 우선, ALSA 카드 목록 차선으로 캡처/재생 장치를 결정합니다."""

    def __init__(
        self,
        capture_override: Optional[str] = None,
        playback_override: Optional[str] = None,
        card_match: Optional[str] = None,
    ) -> None:
        self.capture_override = capture_override or os.getenv("AUDIO_CAPTURE_DEVICE")
        self.playback_override = playback_override or os.getenv("AUDIO_PLAYBACK_DEVICE")
        self.card_match = card_match or os.getenv("AUDIO_CARD_MATCH", DEFAULT_CARD_MATCH)

    def resolve(
        self,
    ) -> tuple[Optional[AlsaDeviceInfo], Optional[AlsaDeviceInfo], Optional[str]]:
        capture = self._override_info(self.capture_override, "AUDIO_CAPTURE_DEVICE")
        playback = self._override_info(self.playback_override, "AUDIO_PLAYBACK_DEVICE")

        if capture and playback:
            return capture, playback, None

        detected = self._detect_card()
        if detected is None:
            missing = []
            if capture is None:
                missing.append("캡처")
            if playback is None:
                missing.append("재생")
            reason = (
                f"{', '.join(missing)} ALSA 장치를 찾지 못했습니다. "
                f"검색 키워드: {self.card_match!r}. "
                "AUDIO_CAPTURE_DEVICE/AUDIO_PLAYBACK_DEVICE로 직접 지정할 수 있습니다."
            )
            return capture, playback, reason

        card_index, card_name, source = detected
        auto_device = f"plughw:{card_index},0"
        if capture is None:
            capture = AlsaDeviceInfo(auto_device, source, card_index, card_name)
        if playback is None:
            playback = AlsaDeviceInfo(auto_device, source, card_index, card_name)
        return capture, playback, None

    @staticmethod
    def _override_info(value: Optional[str], variable_name: str) -> Optional[AlsaDeviceInfo]:
        if not value or not value.strip():
            return None
        return AlsaDeviceInfo(device=value.strip(), source=f"환경변수 {variable_name}")

    def _detect_card(self) -> Optional[tuple[int, str, str]]:
        cards_path = Path("/proc/asound/cards")
        try:
            cards_text = cards_path.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            logger.info("ALSA 카드 파일을 읽을 수 없습니다: %s", error)
        else:
            matched = find_matching_alsa_card(cards_text, self.card_match)
            if matched:
                return matched[0], matched[1], str(cards_path)

        for command in (["arecord", "-l"], ["aplay", "-l"]):
            if shutil.which(command[0]) is None:
                logger.warning("ALSA 명령을 찾을 수 없습니다: %s", command[0])
                continue

            logger.info("ALSA 장치 탐색 명령 실행: %s", _format_command(command))
            try:
                completed = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=5,
                )
            except (OSError, subprocess.SubprocessError) as error:
                logger.warning("ALSA 장치 탐색 명령 실패: %s", error)
                continue

            if completed.stderr.strip():
                logger.warning("ALSA 장치 탐색 오류 출력: %s", completed.stderr.strip())
            matched = find_matching_alsa_card(completed.stdout, self.card_match)
            if matched:
                return matched[0], matched[1], _format_command(command)

        return None


class AudioController:
    """arecord/aplay 프로세스와 하드웨어 상태를 직렬화해 관리합니다."""

    def __init__(
        self,
        resolver: Optional[AlsaDeviceResolver] = None,
        recordings_dir: Optional[Path | str] = None,
        audio_dir: Optional[Path | str] = None,
        popen_factory: Callable[..., subprocess.Popen[str]] = subprocess.Popen,
        recording_completed_hook: Optional[Callable[[Path], None]] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._base_dir = Path(__file__).resolve().parent
        self._resolver = resolver or AlsaDeviceResolver()
        self._popen_factory = popen_factory
        self._recording_completed_hook = recording_completed_hook

        configured_recordings_dir = recordings_dir or os.getenv("AUDIO_RECORDINGS_DIR")
        self.recordings_dir = self._resolve_directory(
            configured_recordings_dir,
            self._base_dir / "recordings",
        )
        self.audio_dir = self._resolve_directory(audio_dir, self._base_dir / "audio")
        self.allowed_playback_dirs = (self.recordings_dir, self.audio_dir)

        self._state: HardwareState = "idle"
        self._record_process: Optional[subprocess.Popen[str]] = None
        self._playback_process: Optional[subprocess.Popen[str]] = None
        self._recording_path: Optional[Path] = None
        self._playback_path: Optional[Path] = None
        self._recording_started_at: Optional[float] = None
        self._last_error: Optional[str] = None
        self._capture_device: Optional[AlsaDeviceInfo] = None
        self._playback_device: Optional[AlsaDeviceInfo] = None
        self._device_error: Optional[str] = None
        self._directory_error: Optional[str] = None

        self._prepare_recordings_directory()
        self.refresh_devices()

    def refresh_devices(self) -> dict[str, object]:
        capture, playback, error = self._resolver.resolve()
        with self._lock:
            self._capture_device = capture
            self._playback_device = playback
            self._device_error = error

        if error:
            logger.warning("ALSA 장치 탐지 실패: %s", error)
        else:
            logger.info(
                "ALSA 장치 탐지 완료: capture=%s, playback=%s",
                capture.device if capture else None,
                playback.device if playback else None,
            )
        return {
            "card_match": self._resolver.card_match,
            "capture": asdict(capture) if capture else None,
            "playback": asdict(playback) if playback else None,
            "error": error,
        }

    def health(self) -> dict[str, object]:
        self.refresh_devices()
        with self._lock:
            self._refresh_record_process_locked()
            devices_ready = self._capture_device is not None and self._playback_device is not None
            return {
                "service": "running",
                "status": "ok" if devices_ready and not self._directory_error else "degraded",
                "alsa": {
                    "card_match": self._resolver.card_match,
                    "capture": asdict(self._capture_device) if self._capture_device else None,
                    "playback": asdict(self._playback_device) if self._playback_device else None,
                    "error": self._device_error,
                },
                "hardware": self._status_locked(),
                "recordings_directory": str(self.recordings_dir),
                "recordings_directory_error": self._directory_error,
            }

    def status(self) -> dict[str, object]:
        with self._lock:
            self._refresh_record_process_locked()
            return self._status_locked()

    def get_status(self) -> dict[str, object]:
        """Agent와 FastAPI 양쪽에서 사용하는 공개 상태 조회 API입니다."""
        return self.status()

    def start_recording(self) -> dict[str, object]:
        self.refresh_devices()
        with self._lock:
            self._refresh_record_process_locked()
            if self._record_process is not None:
                raise AudioConflictError("이미 녹음 중입니다.")
            if self._playback_process is not None:
                raise AudioConflictError("재생 중에는 녹음을 시작할 수 없습니다.")
            if self._directory_error:
                raise AudioUnavailableError(self._directory_error)
            if self._capture_device is None:
                raise AudioUnavailableError(self._device_error or "캡처 ALSA 장치를 찾지 못했습니다.")
            if shutil.which("arecord") is None:
                raise AudioUnavailableError("arecord 실행 파일을 찾지 못했습니다. alsa-utils를 설치해주세요.")

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"recording_{timestamp}_{uuid.uuid4().hex}.wav"
            file_path = self.recordings_dir / file_name
            command = [
                "arecord",
                "-D",
                self._capture_device.device,
                "-c",
                "1",
                "-r",
                "48000",
                "-f",
                "S32_LE",
                "-t",
                "wav",
                str(file_path),
            ]
            logger.info("녹음 명령 실행: %s", _format_command(command))

            try:
                process = self._popen_factory(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
            except OSError as error:
                self._set_error_locked(f"arecord 실행 실패: {error}")
                logger.exception("arecord 프로세스를 시작하지 못했습니다.")
                raise AudioUnavailableError(self._last_error or str(error)) from error

            time.sleep(0.1)
            if process.poll() is not None:
                error_output = self._read_stderr(process)
                message = f"arecord가 즉시 종료되었습니다(returncode={process.returncode})."
                if error_output:
                    message = f"{message} {error_output}"
                self._set_error_locked(message)
                logger.error(message)
                raise AudioUnavailableError(message)

            self._record_process = process
            self._recording_path = file_path
            self._recording_started_at = time.monotonic()
            self._state = "recording"
            self._last_error = None
            return {
                "status": self._state,
                "file_path": str(file_path),
                "capture_device": self._capture_device.device,
            }

    def stop_recording(self) -> dict[str, object]:
        with self._lock:
            self._refresh_record_process_locked()
            if self._record_process is None or self._state != "recording":
                raise AudioConflictError("현재 녹음 중이 아닙니다.")

            process = self._record_process
            file_path = self._recording_path
            elapsed = (
                time.monotonic() - self._recording_started_at
                if self._recording_started_at is not None
                else 0.0
            )
            returncode, error_output = self._stop_process(process, "arecord")
            self._record_process = None
            self._recording_path = None
            self._recording_started_at = None

            if error_output:
                log_method = logger.warning if returncode not in (0, None) else logger.info
                log_method("arecord 종료 출력: %s", error_output)

            if file_path is None:
                self._set_error_locked("녹음 파일 경로가 상태에서 누락되었습니다.")
                raise InvalidRecordingError(self._last_error or "녹음 파일 경로 누락")

            try:
                result = self._validate_recording(file_path)
            except InvalidRecordingError as error:
                self._set_error_locked(str(error))
                logger.error("녹음 파일 검증 실패: %s", error)
                raise

            self._state = "idle"
            self._last_error = None

        logger.info(
            "녹음 완료: path=%s, size=%s, audio_duration=%.3f, elapsed=%.3f",
            result.file_path,
            result.size_bytes,
            result.duration_seconds,
            elapsed,
        )
        self._notify_recording_completed(file_path)
        return {
            "status": "idle",
            "file_path": result.file_path,
            "size_bytes": result.size_bytes,
            "duration_seconds": result.duration_seconds,
        }

    def play(self, requested_path: str) -> dict[str, object]:
        file_path = self._validate_playback_path(requested_path)
        self.refresh_devices()

        with self._lock:
            self._refresh_record_process_locked()
            if self._record_process is not None:
                raise AudioConflictError("녹음 중에는 오디오를 재생할 수 없습니다.")
            if self._playback_device is None:
                raise AudioUnavailableError(self._device_error or "재생 ALSA 장치를 찾지 못했습니다.")
            if shutil.which("aplay") is None:
                raise AudioUnavailableError("aplay 실행 파일을 찾지 못했습니다. alsa-utils를 설치해주세요.")

            replaced_file = None
            if self._playback_process is not None:
                replaced_file = str(self._playback_path) if self._playback_path else None
                self._stop_playback_locked("새 재생 요청으로 기존 재생 중지")

            command = ["aplay", "-D", self._playback_device.device, str(file_path)]
            logger.info("재생 명령 실행: %s", _format_command(command))
            try:
                process = self._popen_factory(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
            except OSError as error:
                self._set_error_locked(f"aplay 실행 실패: {error}")
                logger.exception("aplay 프로세스를 시작하지 못했습니다.")
                raise AudioUnavailableError(self._last_error or str(error)) from error

            time.sleep(0.05)
            if process.poll() is not None and process.returncode != 0:
                error_output = self._read_stderr(process)
                message = f"aplay가 즉시 종료되었습니다(returncode={process.returncode})."
                if error_output:
                    message = f"{message} {error_output}"
                self._set_error_locked(message)
                logger.error(message)
                raise AudioUnavailableError(message)

            self._playback_process = process
            self._playback_path = file_path
            self._state = "playing"
            self._last_error = None
            watcher = threading.Thread(
                target=self._watch_playback,
                args=(process, file_path),
                name=f"aplay-watcher-{process.pid}",
                daemon=True,
            )
            watcher.start()

            return {
                "status": "playing",
                "file_path": str(file_path),
                "playback_device": self._playback_device.device,
                "replaced_file_path": replaced_file,
                "policy": "새 재생 요청은 기존 재생을 중지하고 교체합니다.",
            }

    def play_file(self, file_path: str) -> dict[str, object]:
        """Agent가 사용하는 공개 재생 API입니다."""
        return self.play(file_path)

    def stop_playback(self) -> dict[str, object]:
        with self._lock:
            if self._playback_process is None or self._state != "playing":
                raise AudioConflictError("현재 재생 중이 아닙니다.")
            stopped_path = str(self._playback_path) if self._playback_path else None
            self._stop_playback_locked("재생 중지 API 요청")
            return {"status": "idle", "stopped_file_path": stopped_path}

    def list_recordings(self, limit: int = 20) -> list[dict[str, object]]:
        self._prepare_recordings_directory()
        if self._directory_error:
            raise AudioUnavailableError(self._directory_error)

        files = sorted(
            (path for path in self.recordings_dir.glob("*.wav") if path.is_file()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )[:limit]
        recordings = []
        for path in files:
            stat = path.stat()
            recordings.append(
                {
                    "file_name": path.name,
                    "file_path": str(path),
                    "created_at": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(),
                    "size_bytes": stat.st_size,
                }
            )

        # TODO: 보존 기간/최대 용량 정책이 정해지면 이 지점에 오래된 파일 정리 전략을 연결합니다.
        return recordings

    def shutdown(self) -> None:
        logger.info("하드웨어 오디오 컨트롤러 종료를 시작합니다.")
        try:
            with self._lock:
                if self._record_process is not None:
                    self._stop_process(self._record_process, "arecord")
                    self._record_process = None
                    self._recording_path = None
                    self._recording_started_at = None
                if self._playback_process is not None:
                    self._stop_playback_locked("서버 종료")
                self._state = "idle"
        except Exception:
            logger.exception("하드웨어 프로세스 종료 중 오류가 발생했습니다.")

    def _status_locked(self) -> dict[str, object]:
        effective_error = self._last_error or self._device_error or self._directory_error
        effective_state: HardwareState = self._state
        if effective_state == "idle" and effective_error:
            effective_state = "error"
        return {
            "state": effective_state,
            "recording_file_path": str(self._recording_path) if self._recording_path else None,
            "playback_file_path": str(self._playback_path) if self._playback_path else None,
            "last_error": effective_error,
        }

    def _refresh_record_process_locked(self) -> None:
        if self._record_process is None or self._record_process.poll() is None:
            return
        process = self._record_process
        error_output = self._read_stderr(process)
        message = f"arecord가 예기치 않게 종료되었습니다(returncode={process.returncode})."
        if error_output:
            message = f"{message} {error_output}"
        self._record_process = None
        self._recording_path = None
        self._recording_started_at = None
        self._set_error_locked(message)
        logger.error(message)

    def _watch_playback(self, process: subprocess.Popen[str], file_path: Path) -> None:
        returncode = process.wait()
        error_output = self._read_stderr(process)
        if error_output:
            log_method = logger.warning if returncode else logger.info
            log_method("aplay 종료 출력: %s", error_output)

        with self._lock:
            if self._playback_process is not process:
                return
            self._playback_process = None
            self._playback_path = None
            if returncode == 0:
                self._state = "idle"
                self._last_error = None
                logger.info("오디오 재생 완료: %s", file_path)
            else:
                message = f"aplay 재생 실패(returncode={returncode}): {file_path}"
                if error_output:
                    message = f"{message} - {error_output}"
                self._set_error_locked(message)
                logger.error(message)

    def _stop_playback_locked(self, reason: str) -> None:
        process = self._playback_process
        if process is None:
            return
        logger.info("aplay 중지: %s", reason)
        self._playback_process = None
        returncode, error_output = self._stop_process(process, "aplay")
        if error_output:
            log_method = logger.warning if returncode not in (0, None) else logger.info
            log_method("aplay 중지 출력: %s", error_output)
        self._playback_path = None
        self._state = "idle"
        self._last_error = None

    @staticmethod
    def _stop_process(
        process: subprocess.Popen[str],
        process_name: str,
    ) -> tuple[Optional[int], str]:
        if process.poll() is None:
            logger.info("%s 프로세스에 SIGINT를 전송합니다(pid=%s).", process_name, process.pid)
            try:
                process.send_signal(signal.SIGINT)
                process.wait(timeout=5)
            except ProcessLookupError:
                pass
            except subprocess.TimeoutExpired:
                logger.warning("%s SIGINT 종료가 지연되어 terminate를 실행합니다.", process_name)
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    logger.error("%s terminate가 실패하여 kill을 실행합니다.", process_name)
                    process.kill()
                    process.wait(timeout=2)

        return process.returncode, AudioController._read_stderr(process)

    @staticmethod
    def _read_stderr(process: subprocess.Popen[str]) -> str:
        if process.stderr is None:
            return ""
        try:
            return process.stderr.read().strip()
        except (OSError, ValueError):
            return ""

    def _validate_recording(self, file_path: Path) -> RecordingResult:
        try:
            size_bytes = file_path.stat().st_size
        except OSError as error:
            raise InvalidRecordingError(f"녹음 파일을 확인할 수 없습니다: {error}") from error
        if size_bytes <= 44:
            raise InvalidRecordingError(f"녹음 파일이 비어 있거나 너무 작습니다: {file_path}")

        try:
            with wave.open(str(file_path), "rb") as wav_file:
                channels = wav_file.getnchannels()
                sample_rate = wav_file.getframerate()
                sample_width = wav_file.getsampwidth()
                frame_count = wav_file.getnframes()
        except (EOFError, OSError, wave.Error) as error:
            raise InvalidRecordingError(f"정상 WAV 파일이 아닙니다: {file_path} ({error})") from error

        if channels != 1 or sample_rate != 48000 or sample_width != 4 or frame_count <= 0:
            raise InvalidRecordingError(
                "WAV 형식이 예상과 다릅니다: "
                f"channels={channels}, rate={sample_rate}, sample_width={sample_width}, frames={frame_count}"
            )

        duration_seconds = frame_count / sample_rate
        return RecordingResult(str(file_path), size_bytes, round(duration_seconds, 3))

    def _validate_playback_path(self, requested_path: str) -> Path:
        if not requested_path or not requested_path.strip():
            raise AudioPathNotAllowedError("재생할 WAV 파일 경로가 필요합니다.")

        candidate = Path(requested_path.strip()).expanduser()
        if not candidate.is_absolute():
            candidate = self._base_dir / candidate
        candidate = candidate.resolve(strict=False)

        if not any(self._is_relative_to(candidate, root) for root in self.allowed_playback_dirs):
            allowed = ", ".join(str(root) for root in self.allowed_playback_dirs)
            raise AudioPathNotAllowedError(f"허용된 오디오 폴더 밖의 경로입니다. 허용 폴더: {allowed}")
        if not candidate.exists() or not candidate.is_file():
            raise AudioFileNotFoundError(f"재생할 파일이 없습니다: {candidate}")
        if candidate.suffix.lower() != ".wav":
            raise AudioPathNotAllowedError("WAV 파일만 재생할 수 있습니다.")
        return candidate

    def _notify_recording_completed(self, file_path: Path) -> None:
        if self._recording_completed_hook:
            try:
                self._recording_completed_hook(file_path)
            except Exception:
                logger.exception("녹음 완료 후처리 훅 실행에 실패했습니다: %s", file_path)
            return

        # TODO: 백엔드 업로드 API 명세가 확정되면 이 훅에 전송 함수를 주입합니다.
        logger.info("녹음 완료 후처리 대기(TODO: 백엔드 전송 연동): %s", file_path)

    def _prepare_recordings_directory(self) -> None:
        try:
            self.recordings_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            self._directory_error = f"녹음 폴더를 준비할 수 없습니다: {self.recordings_dir} ({error})"
            logger.error(self._directory_error)
        else:
            self._directory_error = None

    def _set_error_locked(self, message: str) -> None:
        self._state = "error"
        self._last_error = message

    def _resolve_directory(self, value: Optional[Path | str], default: Path) -> Path:
        if value is None or not str(value).strip():
            return default.resolve(strict=False)
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = self._base_dir / path
        return path.resolve(strict=False)

    @staticmethod
    def _is_relative_to(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root.resolve(strict=False))
        except ValueError:
            return False
        return True
