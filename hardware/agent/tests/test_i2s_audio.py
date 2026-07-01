import os
import sys
import unittest
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

import i2s_audio


class I2SAudioCommandTests(unittest.TestCase):
    def test_arecord_command_uses_i2s_format(self):
        command = i2s_audio.build_arecord_command("/tmp/input.wav", device="plughw:2,0")

        self.assertEqual(
            command,
            [
                "arecord",
                "-D",
                "plughw:2,0",
                "-c",
                "1",
                "-r",
                "16000",
                "-f",
                "S16_LE",
                "-t",
                "wav",
                "/tmp/input.wav",
            ],
        )

    def test_aplay_command_uses_selected_i2s_device(self):
        command = i2s_audio.build_aplay_command("/tmp/reply.wav", device="plughw:2,0")

        self.assertEqual(command, ["aplay", "-D", "plughw:2,0", "/tmp/reply.wav"])

    def test_proc_asound_cards_detection_finds_google_voicehat(self):
        cards = """
 0 [vc4hdmi        ]: vc4-hdmi - vc4-hdmi
                      vc4-hdmi
 2 [googlevoicehat ]: simple-card - Google voiceHAT Soundcard
                      Google voiceHAT Soundcard
"""

        self.assertEqual(i2s_audio._card_number_from_proc_cards(cards, "Google voiceHAT Soundcard"), 2)

    def test_alsa_list_detection_finds_googlevoicehat_alias(self):
        alsa_list = """
card 0: vc4hdmi [vc4-hdmi], device 0: MAI PCM i2s-hifi-0 []
card 2: googlevoicehat [Google voiceHAT Soundcard], device 0: bcm2835-i2s-voicehat-hifi voicehat-hifi-0 []
"""

        self.assertEqual(i2s_audio._card_number_from_alsa_list(alsa_list, "googlevoicehat"), 2)

    def test_environment_device_override_skips_card_discovery(self):
        previous_capture = os.environ.get("AUDIO_CAPTURE_DEVICE")
        previous_playback = os.environ.get("AUDIO_PLAYBACK_DEVICE")
        os.environ["AUDIO_CAPTURE_DEVICE"] = "plughw:9,0"
        os.environ["AUDIO_PLAYBACK_DEVICE"] = "plughw:8,0"
        try:
            self.assertEqual(i2s_audio.resolve_capture_device(), "plughw:9,0")
            self.assertEqual(i2s_audio.resolve_playback_device(), "plughw:8,0")
        finally:
            if previous_capture is None:
                os.environ.pop("AUDIO_CAPTURE_DEVICE", None)
            else:
                os.environ["AUDIO_CAPTURE_DEVICE"] = previous_capture
            if previous_playback is None:
                os.environ.pop("AUDIO_PLAYBACK_DEVICE", None)
            else:
                os.environ["AUDIO_PLAYBACK_DEVICE"] = previous_playback


if __name__ == "__main__":
    unittest.main()
