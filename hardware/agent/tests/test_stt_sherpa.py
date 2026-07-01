import os
import sys
import tempfile
import types
import unittest
import wave
from pathlib import Path
from unittest.mock import patch


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

import stt_sherpa


class FakeStream:
    def __init__(self):
        self.result = types.SimpleNamespace(text="")
        self.accepted = []

    def accept_waveform(self, sample_rate, samples):
        self.accepted.append((sample_rate, samples))


class FakeRecognizer:
    load_calls = 0

    @classmethod
    def from_transducer(cls, **kwargs):
        cls.load_calls += 1
        cls.kwargs = kwargs
        return cls()

    def create_stream(self):
        return FakeStream()

    def decode_streams(self, streams):
        for stream in streams:
            stream.result.text = "오늘은 손주와 공원에 다녀왔어요"


class SherpaSttModuleTests(unittest.TestCase):
    def setUp(self):
        FakeRecognizer.load_calls = 0
        sys.modules.pop("sherpa_onnx", None)

    def tearDown(self):
        sys.modules.pop("sherpa_onnx", None)

    def _write_wav(self, path: Path, sample_rate: int = 16000, sample_width: int = 2):
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(b"\x00\x00" * sample_rate)

    def _write_model_files(self, model_dir: Path):
        for filename in (
            "encoder-epoch-99-avg-1.int8.onnx",
            "decoder-epoch-99-avg-1.int8.onnx",
            "joiner-epoch-99-avg-1.int8.onnx",
            "tokens.txt",
        ):
            (model_dir / filename).write_text("mock", encoding="utf-8")

    def test_config_uses_env_model_dir_and_thread_count(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            old_model_dir = os.environ.get("SHERPA_MODEL_DIR")
            old_threads = os.environ.get("SHERPA_NUM_THREADS")
            os.environ["SHERPA_MODEL_DIR"] = tmp_dir
            os.environ["SHERPA_NUM_THREADS"] = "3"
            try:
                config = stt_sherpa.config_from_env()
            finally:
                if old_model_dir is None:
                    os.environ.pop("SHERPA_MODEL_DIR", None)
                else:
                    os.environ["SHERPA_MODEL_DIR"] = old_model_dir
                if old_threads is None:
                    os.environ.pop("SHERPA_NUM_THREADS", None)
                else:
                    os.environ["SHERPA_NUM_THREADS"] = old_threads

        self.assertEqual(config.model_dir, Path(tmp_dir))
        self.assertEqual(config.num_threads, 3)

    def test_default_threads_are_capped_at_four_cores(self):
        with patch("stt_sherpa.os.cpu_count", return_value=8):
            self.assertEqual(stt_sherpa._default_num_threads(), 4)
        with patch("stt_sherpa.os.cpu_count", return_value=2):
            self.assertEqual(stt_sherpa._default_num_threads(), 2)

    def test_model_file_discovery_uses_int8_files_and_tokens(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            model_dir = Path(tmp_dir)
            self._write_model_files(model_dir)

            files = stt_sherpa.resolve_model_files(model_dir)

        self.assertTrue(files.encoder.name.endswith(".int8.onnx"))
        self.assertTrue(files.decoder.name.endswith(".int8.onnx"))
        self.assertTrue(files.joiner.name.endswith(".int8.onnx"))
        self.assertEqual(files.tokens.name, "tokens.txt")

    def test_model_file_discovery_reports_missing_model_dir(self):
        with self.assertRaises(stt_sherpa.SherpaSttError) as raised:
            stt_sherpa.resolve_model_files(Path("/path/that/does/not/exist"))

        self.assertEqual(raised.exception.code, "MISSING_MODEL_DIR")

    def test_inspect_wav_accepts_16k_16bit_mono(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            wav_path = Path(tmp_dir) / "sample.wav"
            self._write_wav(wav_path)

            info = stt_sherpa.inspect_wav(wav_path)

        self.assertEqual(info.channels, 1)
        self.assertEqual(info.sample_rate, 16000)
        self.assertEqual(info.sample_width_bytes, 2)
        self.assertAlmostEqual(info.duration_seconds, 1.0, places=2)

    def test_inspect_wav_uses_actual_pcm_length_when_header_frame_count_is_placeholder(self):
        class FakeWaveFile:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def getnchannels(self):
                return 1

            def getsampwidth(self):
                return 2

            def getframerate(self):
                return 16000

            def getnframes(self):
                return 1_073_741_760

            def getcomptype(self):
                return "NONE"

            def readframes(self, _frames):
                return b"\x00\x00" * 16000 * 12

        with tempfile.TemporaryDirectory() as tmp_dir:
            wav_path = Path(tmp_dir) / "placeholder.wav"
            wav_path.write_bytes(b"0" * 4096)

            with patch("stt_sherpa.wave.open", return_value=FakeWaveFile()):
                info = stt_sherpa.inspect_wav(wav_path)

        self.assertEqual(info.frames, 16000 * 12)
        self.assertAlmostEqual(info.duration_seconds, 12.0, places=2)

    def test_inspect_wav_rejects_non_16bit_pcm(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            wav_path = Path(tmp_dir) / "sample.wav"
            self._write_wav(wav_path, sample_width=4)

            with self.assertRaises(stt_sherpa.SherpaSttError) as raised:
                stt_sherpa.inspect_wav(wav_path)

        self.assertEqual(raised.exception.code, "UNSUPPORTED_SAMPLE_WIDTH")

    def test_transcriber_loads_model_once_and_reuses_it(self):
        fake_sherpa = types.ModuleType("sherpa_onnx")
        fake_sherpa.OfflineRecognizer = FakeRecognizer
        sys.modules["sherpa_onnx"] = fake_sherpa

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            model_dir = root / "model"
            model_dir.mkdir()
            self._write_model_files(model_dir)
            wav_path = root / "sample.wav"
            self._write_wav(wav_path)

            config = stt_sherpa.SherpaConfig(model_dir=model_dir, num_threads=2)
            transcriber = stt_sherpa.SherpaOnnxKoreanTranscriber(config)

            first = transcriber.transcribe(wav_path)
            second = transcriber.transcribe(wav_path)

        self.assertEqual(first.text, "오늘은 손주와 공원에 다녀왔어요")
        self.assertEqual(second.text, "오늘은 손주와 공원에 다녀왔어요")
        self.assertTrue(first.model_loaded_now)
        self.assertFalse(second.model_loaded_now)
        self.assertEqual(FakeRecognizer.load_calls, 1)
        self.assertEqual(FakeRecognizer.kwargs["num_threads"], 2)

    def test_missing_sherpa_package_is_reported_at_stt_time(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            model_dir = root / "model"
            model_dir.mkdir()
            self._write_model_files(model_dir)
            wav_path = root / "sample.wav"
            self._write_wav(wav_path)

            config = stt_sherpa.SherpaConfig(model_dir=model_dir, num_threads=2)
            transcriber = stt_sherpa.SherpaOnnxKoreanTranscriber(config)

            real_import = __import__

            def fake_import(name, *args, **kwargs):
                if name == "sherpa_onnx":
                    raise ImportError("mock missing sherpa_onnx")
                return real_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=fake_import):
                with self.assertRaises(stt_sherpa.SherpaSttError) as raised:
                    transcriber.transcribe(wav_path)

        self.assertEqual(raised.exception.code, "MISSING_SHERPA_ONNX")


if __name__ == "__main__":
    unittest.main()
