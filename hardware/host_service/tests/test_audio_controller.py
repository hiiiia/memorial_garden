import io
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import wave
from pathlib import Path
from unittest.mock import patch


REPO_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_DIR))

from hardware.host_service import (
    AlsaDeviceInfo,
    AlsaDeviceResolver,
    AudioConflictError,
    AudioController,
    AudioFileNotFoundError,
    AudioPathNotAllowedError,
    find_matching_alsa_card,
)


class StaticResolver:
    card_match = "Google voiceHAT Soundcard"

    def resolve(self):
        device = AlsaDeviceInfo(
            device="plughw:7,0",
            source="test",
            card_index=7,
            card_name="Google voiceHAT Soundcard",
        )
        return device, device, None


class MissingResolver:
    card_match = "Google voiceHAT Soundcard"

    def resolve(self):
        return None, None, "테스트 ALSA 장치 탐지 실패"


class FakeRecordingProcess:
    pid = 4321

    def __init__(self, command, **kwargs):
        self.command = command
        self.kwargs = kwargs
        self.returncode = None
        self.stderr = io.StringIO("")
        output_path = Path(command[-1])
        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(4)
            wav_file.setframerate(48000)
            wav_file.writeframes(b"\0" * 4800 * 4)

    def poll(self):
        return self.returncode

    def send_signal(self, _signal):
        self.returncode = 0

    def wait(self, timeout=None):
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    def terminate(self):
        self.returncode = 0

    def kill(self):
        self.returncode = -9


class FakePlaybackProcess:
    next_pid = 5000

    def __init__(self, command, **kwargs):
        self.command = command
        self.kwargs = kwargs
        self.returncode = None
        self.stderr = io.StringIO("")
        self.finished = threading.Event()
        self.pid = FakePlaybackProcess.next_pid
        FakePlaybackProcess.next_pid += 1

    def poll(self):
        return self.returncode

    def send_signal(self, _signal):
        self.returncode = 0
        self.finished.set()

    def wait(self, timeout=None):
        if not self.finished.wait(timeout):
            raise subprocess.TimeoutExpired(self.command, timeout)
        return self.returncode

    def terminate(self):
        self.send_signal(None)

    def kill(self):
        self.returncode = -9
        self.finished.set()


class AlsaDetectionTests(unittest.TestCase):
    def test_proc_asound_cards_parsing(self):
        cards = """
 0 [vc4hdmi0      ]: vc4-hdmi - vc4-hdmi-0
                      vc4-hdmi-0
 7 [sndrpigooglevoi]: RPi-simple - snd_rpi_googlevoicehat_soundcard
                      Google voiceHAT Soundcard
"""
        self.assertEqual(
            find_matching_alsa_card(cards, "Google voiceHAT Soundcard"),
            (7, "RPi-simple - snd_rpi_googlevoicehat_soundcard"),
        )

    def test_arecord_list_parsing_with_normalized_alias(self):
        devices = (
            "card 3: sndrpigooglevoi [Google voiceHAT Soundcard], "
            "device 0: Google voiceHAT SoundCard HiFi multicodec-0 [Google voiceHAT SoundCard HiFi]"
        )
        self.assertEqual(
            find_matching_alsa_card(devices, "googlevoicehat"),
            (3, "Google voiceHAT Soundcard"),
        )

    def test_explicit_device_overrides_take_priority(self):
        resolver = AlsaDeviceResolver(
            capture_override="hw:CARD=capture,DEV=0",
            playback_override="plughw:CARD=playback,DEV=0",
        )
        capture, playback, error = resolver.resolve()
        self.assertIsNone(error)
        self.assertEqual(capture.device, "hw:CARD=capture,DEV=0")
        self.assertEqual(playback.device, "plughw:CARD=playback,DEV=0")

    def test_audio_controller_package_import_is_available(self):
        from hardware.host_service.audio_controller import AudioController as ImportedController

        self.assertIs(ImportedController, AudioController)


class AudioControllerTests(unittest.TestCase):
    def test_missing_alsa_keeps_service_degraded_with_error_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller = AudioController(
                resolver=MissingResolver(),
                recordings_dir=Path(temp_dir) / "recordings",
            )
            health = controller.health()
            self.assertEqual(health["status"], "degraded")
            self.assertEqual(health["hardware"]["state"], "error")
            self.assertEqual(health["hardware"]["last_error"], "테스트 ALSA 장치 탐지 실패")

    def test_recording_start_stop_and_conflict(self):
        processes = []

        def process_factory(command, **kwargs):
            process = FakeRecordingProcess(command, **kwargs)
            processes.append(process)
            return process

        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "hardware.host_service.audio_controller.shutil.which", return_value="/usr/bin/arecord"
        ):
            controller = AudioController(
                resolver=StaticResolver(),
                recordings_dir=Path(temp_dir) / "recordings",
                audio_dir=Path(temp_dir) / "audio",
                popen_factory=process_factory,
            )
            refreshed = controller.refresh_devices()
            self.assertEqual(refreshed["capture"]["device"], "plughw:7,0")

            started = controller.start_recording()
            self.assertEqual(started["status"], "recording")
            self.assertIn("recording_", Path(started["file_path"]).name)
            with self.assertRaises(AudioConflictError):
                controller.start_recording()

            stopped = controller.stop_recording()
            self.assertEqual(stopped["status"], "idle")
            self.assertGreater(stopped["size_bytes"], 44)
            self.assertEqual(stopped["duration_seconds"], 0.1)
            self.assertEqual(controller.get_status()["state"], "idle")

            command = processes[0].command
            self.assertEqual(command[:3], ["arecord", "-D", "plughw:7,0"])
            self.assertIn("S32_LE", command)
            self.assertNotIn("shell", processes[0].kwargs)

    def test_playback_path_must_stay_in_allowed_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            controller = AudioController(
                resolver=StaticResolver(),
                recordings_dir=temp_path / "recordings",
                audio_dir=temp_path / "audio",
            )
            allowed_file = controller.recordings_dir / "allowed.wav"
            allowed_file.write_bytes(b"RIFF-test")
            self.assertEqual(controller._validate_playback_path(str(allowed_file)), allowed_file)

            with self.assertRaises(AudioFileNotFoundError):
                controller._validate_playback_path(str(controller.recordings_dir / "missing.wav"))
            with self.assertRaises(AudioPathNotAllowedError):
                controller._validate_playback_path(str(temp_path / "outside.wav"))

    def test_new_playback_replaces_previous_process_and_can_stop(self):
        processes = []

        def process_factory(command, **kwargs):
            process = FakePlaybackProcess(command, **kwargs)
            processes.append(process)
            return process

        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "hardware.host_service.audio_controller.shutil.which", return_value="/usr/bin/aplay"
        ):
            controller = AudioController(
                resolver=StaticResolver(),
                recordings_dir=Path(temp_dir) / "recordings",
                popen_factory=process_factory,
            )
            first_file = controller.recordings_dir / "first.wav"
            second_file = controller.recordings_dir / "second.wav"
            first_file.write_bytes(b"RIFF-first")
            second_file.write_bytes(b"RIFF-second")

            first_result = controller.play(str(first_file))
            self.assertEqual(first_result["status"], "playing")
            self.assertEqual(controller.get_status()["state"], "playing")

            second_result = controller.play_file(str(second_file))
            self.assertEqual(second_result["replaced_file_path"], str(first_file))
            self.assertTrue(processes[0].finished.is_set())
            self.assertEqual(controller.get_status()["playback_file_path"], str(second_file))

            stopped = controller.stop_playback()
            self.assertEqual(stopped["status"], "idle")
            self.assertTrue(processes[1].finished.is_set())
            self.assertEqual(controller.get_status()["state"], "idle")

    def test_playback_returns_to_idle_after_natural_completion(self):
        processes = []

        def process_factory(command, **kwargs):
            process = FakePlaybackProcess(command, **kwargs)
            processes.append(process)
            return process

        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "hardware.host_service.audio_controller.shutil.which", return_value="/usr/bin/aplay"
        ):
            controller = AudioController(
                resolver=StaticResolver(),
                recordings_dir=Path(temp_dir) / "recordings",
                popen_factory=process_factory,
            )
            audio_file = controller.recordings_dir / "complete.wav"
            audio_file.write_bytes(b"RIFF-complete")
            controller.play(str(audio_file))

            processes[0].returncode = 0
            processes[0].finished.set()
            for _ in range(50):
                if controller.get_status()["state"] == "idle":
                    break
                time.sleep(0.01)

            self.assertEqual(controller.get_status()["state"], "idle")
            self.assertIsNone(controller.get_status()["playback_file_path"])

    def test_recordings_are_sorted_by_mtime(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller = AudioController(
                resolver=StaticResolver(),
                recordings_dir=Path(temp_dir) / "recordings",
            )
            first = controller.recordings_dir / "first.wav"
            second = controller.recordings_dir / "second.wav"
            first.write_bytes(b"one")
            second.write_bytes(b"two")
            os.utime(first, (1_700_000_000, 1_700_000_000))
            os.utime(second, (1_700_000_100, 1_700_000_100))

            recordings = controller.list_recordings(limit=1)
            self.assertEqual(len(recordings), 1)
            self.assertEqual(recordings[0]["file_name"], "second.wav")


class FastApiWrapperTests(unittest.TestCase):
    def test_rest_routes_are_registered_when_fastapi_is_available(self):
        try:
            from hardware.host_service import main as rest_main
        except ModuleNotFoundError as error:
            if error.name in {"fastapi", "dotenv", "pydantic"}:
                self.skipTest(f"FastAPI REST dependency is not installed: {error.name}")
            raise

        route_paths = {route.path for route in rest_main.app.routes}
        expected_paths = {
            "/health",
            "/hardware/status",
            "/hardware/record/start",
            "/hardware/record/stop",
            "/hardware/audio/play",
            "/hardware/audio/stop",
            "/hardware/recordings",
        }
        self.assertTrue(expected_paths.issubset(route_paths))


if __name__ == "__main__":
    unittest.main()
