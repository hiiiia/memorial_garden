import asyncio
import importlib
import json
import os
import sys
import types
import unittest
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_DIR))


class FakeSettings:
    AI_SERVER_URL = "http://ai.test"
    DEPENDENT_ID = "dep_test"
    BACKEND_URL = "http://backend.test"
    RASPI_MAC = "00:11:22:33:44:55"
    AI_TOKEN = "ai-token"
    HW_TOKEN = "hw-token"


class FakeDbManager:
    def __init__(self):
        self.inserted = []

    def search_memory(self, raw_text, limit=1):
        return []

    def insert_memory(self, raw_text):
        self.inserted.append(raw_text)


def install_import_fakes():
    os.environ["HARDWARE_RUNTIME_MODE"] = "docker"
    config_module = types.ModuleType("hardware.agent.src.config")
    config_module.settings = FakeSettings()
    database_module = types.ModuleType("hardware.agent.src.database")
    database_module.db_manager = FakeDbManager()

    websockets_module = types.ModuleType("websockets")
    websockets_module.exceptions = types.SimpleNamespace(ConnectionClosed=ConnectionError)
    websockets_module.serve = None
    websockets_module.connect = None

    aiohttp_module = types.ModuleType("aiohttp")
    aiohttp_module.ClientSession = object
    aiohttp_module.FormData = object

    sys.modules["hardware.agent.src.config"] = config_module
    sys.modules["hardware.agent.src.database"] = database_module
    sys.modules.setdefault("websockets", websockets_module)
    sys.modules.setdefault("aiohttp", aiohttp_module)


class FakeWebsocket:
    def __init__(self):
        self.sent_messages = []

    async def send(self, message):
        self.sent_messages.append(json.loads(message))


class FakeAudioController:
    def __init__(self, initial_state="idle"):
        self.state = initial_state
        self.calls = []

    def refresh_devices(self):
        self.calls.append(("refresh_devices",))
        return {"error": None}

    def get_status(self):
        self.calls.append(("get_status",))
        return {
            "state": self.state,
            "recording_file_path": "/tmp/current.wav" if self.state == "recording" else None,
            "playback_file_path": None,
            "last_error": None,
        }

    def start_recording(self):
        self.calls.append(("start_recording",))
        self.state = "recording"
        return {"status": "recording", "file_path": "/tmp/recording.wav"}

    def stop_recording(self):
        self.calls.append(("stop_recording",))
        self.state = "idle"
        return {
            "status": "idle",
            "file_path": "/tmp/recording.wav",
            "duration_seconds": 1.2,
            "size_bytes": 48044,
        }

    def play_file(self, file_path):
        self.calls.append(("play_file", file_path))
        return {"status": "playing", "file_path": file_path}

    def stop_playback(self):
        self.calls.append(("stop_playback",))
        return {"status": "idle"}


class AgentAudioFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        install_import_fakes()
        self.agent_main = importlib.import_module("hardware.agent.src.main")
        self.agent_main.audio_task_queue = asyncio.Queue()
        self.agent_main.DEPENDENT_ID = "dep_test"
        self.agent_main.TEST_MODE = True
        self.agent_main.TEST_INPUT_TEXT = "오늘 산책을 다녀왔어."

        async def fake_route(_session, raw_text, _memory_context):
            return {"local_reply": f"응답: {raw_text}", "save_flag": False}

        self.agent_main.get_response_from_ai_server = fake_route

    async def test_force_record_first_call_starts_recording_and_returns_listening(self):
        controller = FakeAudioController(initial_state="idle")
        self.agent_main.audio_controller = controller
        websocket = FakeWebsocket()

        await self.agent_main.handle_force_record_command(websocket, session=object(), async_tasks=set())

        self.assertIn(("start_recording",), controller.calls)
        self.assertEqual(websocket.sent_messages[-1]["status"], "listening")
        self.assertEqual(websocket.sent_messages[-1]["file_path"], "/tmp/recording.wav")

    async def test_force_record_second_call_stops_recording_and_queues_upload(self):
        controller = FakeAudioController(initial_state="recording")
        self.agent_main.audio_controller = controller
        websocket = FakeWebsocket()

        await self.agent_main.handle_force_record_command(websocket, session=object(), async_tasks=set())

        statuses = [message["status"] for message in websocket.sent_messages]
        self.assertIn("processing", statuses)
        self.assertIn("speaking", statuses)
        self.assertEqual(statuses[-1], "idle")
        self.assertIn(("stop_recording",), controller.calls)

        queued = await self.agent_main.audio_task_queue.get()
        self.assertEqual(queued["wav_path"], "/tmp/recording.wav")
        self.assertEqual(queued["user_id"], "dep_test")
        self.assertEqual(queued["stt_text"], "오늘 산책을 다녀왔어.")

    async def test_play_local_action_calls_audio_controller(self):
        controller = FakeAudioController(initial_state="idle")
        self.agent_main.audio_controller = controller

        await self.agent_main.play_local_action("/tmp/guide.wav")

        self.assertIn(("play_file", "/tmp/guide.wav"), controller.calls)

    def test_docker_mode_audio_controller_returns_clear_error(self):
        controller = self.agent_main.create_audio_controller("docker")

        with self.assertRaises(self.agent_main.AgentAudioError) as context:
            controller.start_recording()

        self.assertIn("Docker agent 모드", str(context.exception))

    def test_agent_requirements_do_not_include_removed_audio_stack(self):
        requirements = (REPO_DIR / "hardware" / "agent" / "requirements.txt").read_text(encoding="utf-8")
        self.assertNotIn("sounddevice", requirements)
        self.assertNotIn("soundfile", requirements)
        self.assertNotIn("numpy", requirements)


if __name__ == "__main__":
    unittest.main()
