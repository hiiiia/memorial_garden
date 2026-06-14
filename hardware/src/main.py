import argparse
import asyncio

from audio_controller import record_and_upload
from hmi_controller import HMIController, START_RECORD_VP

STATUS_IDLE = "idle"
STATUS_LISTENING = "listening"
STATUS_PROCESSING = "processing"
STATUS_DONE = "done"
STATUS_ERROR = "error"


class HardwareApp:
    def __init__(self, mock=False, real_upload_in_mock=False):
        self.mock = mock
        self.real_upload_in_mock = real_upload_in_mock
        self.hmi = HMIController(mock=mock)
        self.recording_task = None
        self.status = STATUS_IDLE
        self.loop = None

    def set_status_from_worker(self, status):
        if not self.loop:
            return

        asyncio.run_coroutine_threadsafe(self.set_status(status), self.loop)

    async def set_status(self, status):
        self.status = status
        print(f"Hardware status: {status}")
        try:
            self.hmi.switch_page_for_status(status)
        except Exception as error:
            print(f"HMI page switch failed: {error}")

    async def handle_start_record(self, event=None):
        if self.recording_task and not self.recording_task.done():
            print("Recording is already running. Ignoring duplicate START_RECORD event.")
            return

        if self.status in (STATUS_LISTENING, STATUS_PROCESSING):
            print("Hardware is busy. Ignoring duplicate START_RECORD event.")
            return

        print("START_RECORD VP event received")
        self.recording_task = asyncio.create_task(self.run_recording())

    async def run_recording(self):
        loop = asyncio.get_running_loop()
        mock_upload = self.mock and not self.real_upload_in_mock

        try:
            await loop.run_in_executor(
                None,
                record_and_upload,
                self.set_status_from_worker,
                self.mock,
                mock_upload
            )
        except Exception as error:
            print(f"Recording workflow failed: {error}")
            await self.set_status(STATUS_ERROR)

    async def run_mock(self):
        self.hmi.open()
        await self.set_status(STATUS_IDLE)
        print("Mock mode: press ENTER to emit START_RECORD VP event. Press Ctrl+C to exit.")

        while True:
            await asyncio.get_running_loop().run_in_executor(None, input)
            await self.hmi.emit_mock_vp_event(START_RECORD_VP)

    async def run_serial(self):
        self.hmi.register_vp_callback(START_RECORD_VP, self.handle_start_record)
        self.hmi.open()
        await self.set_status(STATUS_IDLE)
        await self.hmi.read_loop()

    async def run(self):
        self.loop = asyncio.get_running_loop()
        self.hmi.register_vp_callback(START_RECORD_VP, self.handle_start_record)

        if self.mock:
            await self.run_mock()
        else:
            await self.run_serial()


def parse_args():
    parser = argparse.ArgumentParser(description="Memorial Garden hardware controller")
    parser.add_argument("--mock", action="store_true", help="Run without a physical DWIN HMI or microphone")
    parser.add_argument(
        "--real-upload-in-mock",
        action="store_true",
        help="Use mock audio in mock mode, but upload the generated WAV to the backend"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    app = HardwareApp(mock=args.mock, real_upload_in_mock=args.real_upload_in_mock)

    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        print("Hardware controller stopped")


if __name__ == "__main__":
    main()
