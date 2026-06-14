import inspect
import os
from dataclasses import dataclass

try:
    import serial
except ImportError:
    serial = None

DWIN_HEADER = b"\x5a\xa5"
DWIN_CMD_WRITE = 0x82
DWIN_CMD_READ_RESPONSE = 0x83

# TODO: HMI 화면 완성 후 DGUS에서 설정한 실제 VP 주소로 변경
START_RECORD_VP = 0x2000
RETRY_RECORD_VP = 0x2001
HOME_VP = 0x2002

# TODO: HMI 화면 완성 후 실제 페이지 번호로 변경
PAGE_IDLE = 0
PAGE_LISTENING = 1
PAGE_PROCESSING = 2
PAGE_DONE = 3
PAGE_ERROR = 4

STATUS_PAGE_MAP = {
    "idle": PAGE_IDLE,
    "listening": PAGE_LISTENING,
    "processing": PAGE_PROCESSING,
    "done": PAGE_DONE,
    "error": PAGE_ERROR,
}


@dataclass
class DWINFrame:
    command: int
    payload: bytes
    raw: bytes


@dataclass
class VPEvent:
    vp_address: int
    value: int
    raw_value: bytes
    frame: DWINFrame = None


class HMIController:
    def __init__(self, port=None, baudrate=None, timeout=0.1, mock=False):
        self.port = port or os.getenv("HMI_SERIAL_PORT", "/dev/ttyAMA0")
        self.baudrate = int(baudrate or os.getenv("HMI_BAUDRATE", "115200"))
        self.timeout = timeout
        self.mock = mock
        self.serial_conn = None
        self._buffer = bytearray()
        self._vp_callbacks = {}

    def open(self):
        if self.mock:
            print("HMI mock mode enabled")
            return

        if self.serial_conn and self.serial_conn.is_open:
            return

        if serial is None:
            raise RuntimeError("pyserial package is required for HMI serial mode")

        self.serial_conn = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.timeout
        )
        print(f"HMI serial connected: {self.port} @ {self.baudrate}")

    def close(self):
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()

    def register_vp_callback(self, vp_address, callback):
        self._vp_callbacks[vp_address] = callback

    async def read_loop(self):
        self.open()
        try:
            while True:
                data = self.serial_conn.read(64)
                if data:
                    await self.feed(data)
        finally:
            self.close()

    async def feed(self, data):
        events = self.parse_vp_events(data)
        for event in events:
            await self.dispatch_event(event)

    def parse_vp_events(self, data):
        frames = self.parse_frames(data)
        events = []

        for frame in frames:
            event = self.parse_vp_event(frame)
            if event:
                events.append(event)

        return events

    def parse_frames(self, data):
        self._buffer.extend(data)
        frames = []

        while True:
            header_index = self._buffer.find(DWIN_HEADER)
            if header_index < 0:
                self._buffer.clear()
                break

            if header_index > 0:
                del self._buffer[:header_index]

            if len(self._buffer) < 3:
                break

            frame_length = self._buffer[2]
            total_length = 3 + frame_length

            if len(self._buffer) < total_length:
                break

            raw = bytes(self._buffer[:total_length])
            del self._buffer[:total_length]

            if frame_length < 1:
                continue

            frames.append(DWINFrame(
                command=raw[3],
                payload=raw[4:],
                raw=raw
            ))

        return frames

    def parse_vp_event(self, frame):
        if frame.command == DWIN_CMD_WRITE and len(frame.payload) >= 2:
            vp_address = (frame.payload[0] << 8) | frame.payload[1]
            raw_value = frame.payload[2:]
            return self._build_vp_event(vp_address, raw_value, frame)

        if frame.command != DWIN_CMD_READ_RESPONSE or len(frame.payload) < 3:
            return None

        vp_address = (frame.payload[0] << 8) | frame.payload[1]
        raw_value = frame.payload[3:]
        return self._build_vp_event(vp_address, raw_value, frame)

    def _build_vp_event(self, vp_address, raw_value, frame):
        value = 0

        if len(raw_value) >= 2:
            value = (raw_value[0] << 8) | raw_value[1]
        elif len(raw_value) == 1:
            value = raw_value[0]

        return VPEvent(
            vp_address=vp_address,
            value=value,
            raw_value=raw_value,
            frame=frame
        )

    async def dispatch_event(self, event):
        callback = self._vp_callbacks.get(event.vp_address)
        if not callback:
            print(f"Unhandled HMI VP event: 0x{event.vp_address:04X}, value={event.value}")
            return

        result = callback(event)
        if inspect.isawaitable(result):
            await result

    async def emit_mock_vp_event(self, vp_address, value=1):
        event = VPEvent(
            vp_address=vp_address,
            value=value,
            raw_value=value.to_bytes(2, byteorder="big")
        )
        await self.dispatch_event(event)

    def write_vp(self, vp_address, data):
        if isinstance(data, int):
            data = data.to_bytes(2, byteorder="big")

        frame_body = bytes([
            DWIN_CMD_WRITE,
            (vp_address >> 8) & 0xFF,
            vp_address & 0xFF,
        ]) + data
        frame = DWIN_HEADER + bytes([len(frame_body)]) + frame_body

        if self.mock:
            print(f"HMI mock write: {frame.hex(' ')}")
            return

        if not self.serial_conn or not self.serial_conn.is_open:
            raise RuntimeError("HMI serial connection is not open")

        self.serial_conn.write(frame)

    def switch_page(self, page_id):
        page_data = b"\x5a\x01" + page_id.to_bytes(2, byteorder="big")
        self.write_vp(0x0084, page_data)

    def switch_page_for_status(self, status):
        page_id = STATUS_PAGE_MAP.get(status)
        if page_id is None:
            return

        self.switch_page(page_id)
