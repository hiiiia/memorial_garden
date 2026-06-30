from __future__ import annotations

import os
import re
import signal
import subprocess
import time
from pathlib import Path
from typing import Optional


DEFAULT_CARD_MATCH = "Google voiceHAT Soundcard"
DEFAULT_RATE = "48000"
DEFAULT_FORMAT = "S32_LE"


class I2SAudioError(RuntimeError):
    """I2S 오디오 장치 제어 중 발생한 오류입니다."""


def _card_match_text() -> str:
    return os.getenv("AUDIO_CARD_MATCH", DEFAULT_CARD_MATCH).strip() or DEFAULT_CARD_MATCH


def _normalize(text: str) -> str:
    return text.casefold().replace(" ", "")


def _match_card_name(text: str, card_match: str) -> bool:
    haystack = _normalize(text)
    needles = {_normalize(card_match), "googlevoicehat"}
    return any(needle and needle in haystack for needle in needles)


def _card_number_from_proc_cards(content: str, card_match: str) -> Optional[int]:
    lines = content.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"\s*(\d+)\s+\[", line)
        if not match:
            continue
        block = line
        if index + 1 < len(lines):
            block += "\n" + lines[index + 1]
        if _match_card_name(block, card_match):
            return int(match.group(1))
    return None


def _card_number_from_alsa_list(content: str, card_match: str) -> Optional[int]:
    for line in content.splitlines():
        match = re.search(r"card\s+(\d+)\s*:", line, flags=re.IGNORECASE)
        if match and _match_card_name(line, card_match):
            return int(match.group(1))
    return None


def find_alsa_card_number(card_match: Optional[str] = None) -> int:
    """카드 이름으로 ALSA card 번호를 찾습니다. HDMI/DSI 연결로 번호가 바뀌는 상황을 피합니다."""

    expected = card_match or _card_match_text()
    proc_cards = Path("/proc/asound/cards")
    if proc_cards.exists():
        found = _card_number_from_proc_cards(proc_cards.read_text(encoding="utf-8", errors="ignore"), expected)
        if found is not None:
            return found

    for command in (["arecord", "-l"], ["aplay", "-l"]):
        try:
            completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=5)
        except (FileNotFoundError, subprocess.SubprocessError):
            continue
        found = _card_number_from_alsa_list(completed.stdout + "\n" + completed.stderr, expected)
        if found is not None:
            return found

    raise I2SAudioError(f"ALSA card not found: {expected}")


def resolve_capture_device() -> str:
    configured = os.getenv("AUDIO_CAPTURE_DEVICE", "").strip()
    if configured:
        return configured
    return f"plughw:{find_alsa_card_number()},0"


def resolve_playback_device() -> str:
    configured = os.getenv("AUDIO_PLAYBACK_DEVICE", "").strip()
    if configured:
        return configured
    return f"plughw:{find_alsa_card_number()},0"


def build_arecord_command(file_path: str, device: Optional[str] = None) -> list[str]:
    return [
        "arecord",
        "-D",
        device or resolve_capture_device(),
        "-c",
        "1",
        "-r",
        DEFAULT_RATE,
        "-f",
        DEFAULT_FORMAT,
        "-t",
        "wav",
        file_path,
    ]


def build_aplay_command(file_path: str, device: Optional[str] = None) -> list[str]:
    return ["aplay", "-D", device or resolve_playback_device(), file_path]


def resolve_allowed_audio_path(file_path: str, base_dir: str) -> Path:
    base = Path(base_dir).resolve()
    candidate = Path(file_path)
    if not candidate.is_absolute():
        candidate = base / file_path
    resolved = candidate.resolve()

    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise I2SAudioError(f"audio file is outside allowed directory: {file_path}") from exc

    if not resolved.exists() or not resolved.is_file():
        raise I2SAudioError(f"audio file not found: {file_path}")
    return resolved


def _stop_process_safely(process: subprocess.Popen, timeout: float = 3.0) -> None:
    if process.poll() is not None:
        return
    try:
        process.send_signal(signal.SIGINT)
        process.wait(timeout=timeout)
        return
    except Exception:
        pass

    if process.poll() is None:
        try:
            process.terminate()
            process.wait(timeout=timeout)
            return
        except Exception:
            pass

    if process.poll() is None:
        process.kill()
        process.wait(timeout=timeout)


class I2SRecorder:
    def __init__(self) -> None:
        self.process: Optional[subprocess.Popen] = None
        self.file_path: Optional[Path] = None
        self.started_at: Optional[float] = None

    def start(self, file_path: str) -> None:
        if self.process and self.process.poll() is None:
            raise I2SAudioError("recording already in progress")

        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        command = build_arecord_command(str(path))
        print(f"[I2S] arecord 시작: {' '.join(command[:-1])} <wav>")
        self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
        self.file_path = path
        self.started_at = time.monotonic()

    def stop(self) -> Path:
        if not self.process or not self.file_path:
            raise I2SAudioError("recording is not in progress")

        process = self.process
        path = self.file_path
        try:
            _stop_process_safely(process)
        finally:
            self.process = None
            self.file_path = None
            self.started_at = None

        if not path.exists() or path.stat().st_size <= 44:
            raise I2SAudioError(f"invalid wav file: {path}")
        return path

    def is_recording(self) -> bool:
        return bool(self.process and self.process.poll() is None)


class I2SPlayer:
    def __init__(self) -> None:
        self.process: Optional[subprocess.Popen] = None

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            _stop_process_safely(self.process)
        self.process = None

    def play(self, file_path: str, base_dir: Optional[str] = None) -> None:
        self.stop()
        target_path = resolve_allowed_audio_path(file_path, base_dir) if base_dir else Path(file_path)
        command = build_aplay_command(str(target_path))
        print(f"[I2S] aplay 시작: {' '.join(command[:-1])} <audio>")
        self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
        self.process.wait()
        self.process = None
