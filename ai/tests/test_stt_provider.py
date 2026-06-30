import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))

from app import stt_provider


class STTProviderTests(unittest.TestCase):
    def test_existing_stt_text_is_used_without_calling_provider(self):
        async def scenario():
            with patch.object(stt_provider, "transcribe_wav", side_effect=AssertionError("provider should not be called")):
                result = await stt_provider.ensure_stt_text("/tmp/input.wav", "  실제 발화  ")
            self.assertEqual(result, "실제 발화")

        asyncio.run(scenario())

    def test_empty_stt_text_calls_internal_stt_provider(self):
        async def scenario():
            async def fake_transcribe(file_path):
                self.assertEqual(file_path, "/tmp/input.wav")
                return "인식된 발화"

            with patch.object(stt_provider, "transcribe_wav", side_effect=fake_transcribe):
                result = await stt_provider.ensure_stt_text("/tmp/input.wav", "")
            self.assertEqual(result, "인식된 발화")

        asyncio.run(scenario())

    def test_extract_response_text_strips_provider_response(self):
        response = type("Response", (), {"text": "  안녕하세요  "})()

        self.assertEqual(stt_provider._extract_response_text(response), "안녕하세요")

    def test_analyze_audio_keeps_endpoint_and_makes_stt_optional(self):
        source = (AI_DIR / "app" / "main.py").read_text(encoding="utf-8")

        self.assertIn('@app.post("/api/v1/analyze/audio"', source)
        self.assertIn('stt_text: str = Form("")', source)
        self.assertIn("resolved_stt_text = await ensure_stt_text(temp_file_path, stt_text)", source)
        self.assertIn('"stt_text": resolved_stt_text', source)


if __name__ == "__main__":
    unittest.main()
