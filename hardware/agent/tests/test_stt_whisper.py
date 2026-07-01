import tempfile
import unittest
import wave
from pathlib import Path

import sys


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

import stt_whisper


class WhisperCppModuleTests(unittest.TestCase):
    def test_build_command_uses_nice_and_korean_base_model(self):
        config = stt_whisper.WhisperCppConfig(
            binary_path=Path("/home/pi/whisper.cpp/build/bin/whisper-cli"),
            model_path=Path("/home/pi/whisper.cpp/models/ggml-base.bin"),
            language="ko",
            threads=3,
            nice=10,
            timeout_seconds=180,
        )

        command = stt_whisper.build_whisper_command(config, "/tmp/input.wav")

        self.assertEqual(command[:3], ["nice", "-n", "10"])
        self.assertEqual(Path(command[3]).as_posix(), "/home/pi/whisper.cpp/build/bin/whisper-cli")
        self.assertEqual(command[4], "-m")
        self.assertEqual(Path(command[5]).as_posix(), "/home/pi/whisper.cpp/models/ggml-base.bin")
        self.assertEqual(command[6], "-f")
        self.assertEqual(Path(command[7]).as_posix(), "/tmp/input.wav")
        self.assertEqual(command[8:], ["-l", "ko", "-t", "3", "-nt"])

    def test_clean_transcript_filters_timestamps_and_runtime_logs(self):
        raw = """
whisper_print_timings: total time = 1000 ms
[00:00:00.000 --> 00:00:02.000] 안녕하세요.
main: processing done
[00:00:02.000 --> 00:00:04.000] 오늘 산책을 다녀왔어요.
"""

        self.assertEqual(stt_whisper.clean_transcript(raw), "안녕하세요. 오늘 산책을 다녀왔어요.")

    def test_inspect_wav_reports_format_warnings_without_rejecting_48k_s32_mono(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            wav_path = Path(tmp_dir) / "sample.wav"
            with wave.open(str(wav_path), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(4)
                wav_file.setframerate(48000)
                wav_file.writeframes(b"\x00\x00\x00\x00" * 48000)

            info = stt_whisper.inspect_wav(wav_path)

        self.assertEqual(info.channels, 1)
        self.assertEqual(info.sample_rate, 48000)
        self.assertEqual(info.sample_width_bytes, 4)
        self.assertTrue(any("16kHz" in warning for warning in info.warnings))
        self.assertTrue(any("16-bit" in warning for warning in info.warnings))

    def test_base_en_model_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            binary = tmp / "whisper-cli"
            model = tmp / "ggml-base.en.bin"
            binary.write_text("#!/bin/sh\n", encoding="utf-8")
            model.write_text("model", encoding="utf-8")

            config = stt_whisper.WhisperCppConfig(
                binary_path=binary,
                model_path=model,
                language="ko",
                threads=3,
                nice=10,
                timeout_seconds=180,
            )

            with self.assertRaises(stt_whisper.WhisperCppError) as raised:
                stt_whisper._validate_config(config)

        self.assertEqual(raised.exception.code, "ENGLISH_ONLY_MODEL")


if __name__ == "__main__":
    unittest.main()
