import asyncio
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


AGENT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = AGENT_DIR / "src"
MAIN_PATH = SRC_DIR / "main.py"


class FakeClientSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeConnectionClosed(Exception):
    pass


class FakeDBManager:
    def __init__(self):
        self.inserted = []

    def search_memory(self, text, limit=1):
        return []

    def insert_memory(self, text):
        self.inserted.append(text)


class FakeWebSocket:
    def __init__(self, messages):
        self.messages = list(messages)
        self.sent = []

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.messages:
            raise StopAsyncIteration
        return self.messages.pop(0)

    async def send(self, message):
        self.sent.append(json.loads(message))


class FakeRecorder:
    def __init__(self):
        self.is_recording = False
        self.start_calls = 0
        self.stop_calls = 0

    def start_recording(self):
        self.start_calls += 1
        self.is_recording = True

    def stop_recording(self, wav_name):
        self.stop_calls += 1
        self.is_recording = False
        return True, "/app/data/audio_test.wav"


def load_agent_main():
    sys.path.insert(0, str(SRC_DIR))

    aiohttp_stub = types.ModuleType("aiohttp")
    aiohttp_stub.ClientSession = FakeClientSession
    aiohttp_stub.FormData = lambda: object()

    websockets_stub = types.ModuleType("websockets")
    websockets_stub.exceptions = types.SimpleNamespace(ConnectionClosed=FakeConnectionClosed)
    websockets_stub.serve = lambda *args, **kwargs: None
    websockets_stub.connect = lambda *args, **kwargs: None

    database_stub = types.ModuleType("database")
    database_stub.db_manager = FakeDBManager()

    sys.modules["aiohttp"] = aiohttp_stub
    sys.modules["websockets"] = websockets_stub
    sys.modules["database"] = database_stub

    module_name = "agent_main_under_test"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, MAIN_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class AgentMainFlowTests(unittest.TestCase):
    def test_existing_websocket_port_and_ai_endpoints_are_preserved(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn('websockets.serve(handle_client, "0.0.0.0", 8765)', source)
        self.assertIn("/api/v1/edge/route", source)
        self.assertIn("/api/v1/analyze/audio", source)
        self.assertNotIn("/api/v1/edge/voice-turn", source)

    def test_legacy_test_audio_execution_path_is_removed(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        for token in ("TEST_MODE", "TEST_INPUT_FILE", "test_1.mp3", "sounddevice", "soundfile", "numpy"):
            self.assertNotIn(token, source)

    def test_force_record_start_stop_preserves_upload_queue_flow(self):
        async def scenario():
            module = load_agent_main()
            fake_recorder = FakeRecorder()
            module.recorder = fake_recorder
            module.DEPENDENT_ID = "dependent-test"
            module.audio_task_queue = asyncio.Queue()
            module.recognize_speech_from_mic = lambda: "mock transcript"
            module.db_manager = FakeDBManager()

            async def fake_route(session, raw_text, memory_context):
                return {"local_reply": "mock reply", "save_flag": False}

            async def fake_play_local_action(action_file):
                raise AssertionError("local action should not run without local_action")

            module.get_response_from_ai_server = fake_route
            module.play_local_action = fake_play_local_action

            websocket = FakeWebSocket(
                [
                    json.dumps({"command": "force_record"}),
                    json.dumps({"command": "force_record"}),
                ]
            )

            with patch("builtins.print"):
                await module.handle_client(websocket)
            queued = await module.audio_task_queue.get()

            self.assertEqual(fake_recorder.start_calls, 1)
            self.assertEqual(fake_recorder.stop_calls, 1)
            self.assertEqual(queued["wav_path"], "/app/data/audio_test.wav")
            self.assertEqual(queued["user_id"], "dependent-test")
            self.assertEqual(queued["stt_text"], "mock transcript")
            self.assertEqual([message["status"] for message in websocket.sent], ["listening", "processing", "speaking", "idle"])

        asyncio.run(scenario())

    def test_no_new_stt_tts_dependencies_were_added(self):
        requirements = (AGENT_DIR / "requirements.txt").read_text(encoding="utf-8").casefold()

        for package_name in ("faster-whisper", "edge-tts"):
            self.assertNotIn(package_name, requirements)


if __name__ == "__main__":
    unittest.main()


