import os
import tempfile
import time
import wave
from pathlib import Path

try:
    import pyaudio
except ImportError:
    pyaudio = None

try:
    import requests
except ImportError:
    requests = None

BACKEND_BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000").strip().rstrip("/")
BACKEND_AUDIO_UPLOAD_URL = os.getenv(
    "BACKEND_AUDIO_UPLOAD_URL",
    f"{BACKEND_BASE_URL}/api/v1/files/audio"
)
USER_ID = os.getenv("USER_ID", os.getenv("DEPENDENT_ID", "local-user"))
DEVICE_ID = os.getenv("DEVICE_ID", "raspberry-pi")
API_SECRET_TOKEN = os.getenv("API_SECRET_TOKEN", "default-token")
RECORD_SECONDS = int(os.getenv("RECORD_SECONDS", "5"))
MOCK_RECORD_SECONDS = int(os.getenv("MOCK_RECORD_SECONDS", "1"))
BACKEND_TIMEOUT_SECONDS = int(os.getenv("BACKEND_TIMEOUT_SECONDS", "30"))

CHUNK = 1024
FORMAT = pyaudio.paInt16 if pyaudio else 8
CHANNELS = 1
RATE = 16000
SAMPLE_WIDTH_BYTES = 2


def _notify_status(status_callback, status):
    if status_callback:
        status_callback(status)
    print(f"Audio status: {status}")


def create_mock_wav(duration_seconds=MOCK_RECORD_SECONDS):
    output_path = Path(tempfile.gettempdir()) / f"mock_recording_{int(time.time())}.wav"
    silent_frame_count = RATE * duration_seconds

    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(SAMPLE_WIDTH_BYTES)
        wav_file.setframerate(RATE)
        wav_file.writeframes(b"\x00\x00" * silent_frame_count)

    return output_path


def record_audio(mock=False):
    if mock or pyaudio is None:
        return create_mock_wav()

    output_path = Path(tempfile.gettempdir()) / f"recording_{int(time.time())}.wav"
    audio = pyaudio.PyAudio()
    sample_width = audio.get_sample_size(FORMAT)
    stream = None
    frames = []

    try:
        stream = audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
        chunk_count = int(RATE / CHUNK * RECORD_SECONDS)

        for _ in range(chunk_count):
            frames.append(stream.read(CHUNK, exception_on_overflow=False))
    finally:
        if stream is not None:
            stream.stop_stream()
            stream.close()
        audio.terminate()

    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(RATE)
        wav_file.writeframes(b"".join(frames))

    return output_path


def upload_audio(audio_path, mock=False):
    if mock:
        print(f"Mock upload completed: {audio_path}")
        return {"mock": True, "file_path": str(audio_path)}

    if requests is None:
        raise RuntimeError("requests package is required for backend upload")

    with open(audio_path, "rb") as audio_file:
        response = requests.post(
            BACKEND_AUDIO_UPLOAD_URL,
            headers={"Authorization": f"Bearer {API_SECRET_TOKEN}"},
            data={"user_id": USER_ID, "device_id": DEVICE_ID},
            files={"audio_file": (audio_path.name, audio_file, "audio/wav")},
            timeout=BACKEND_TIMEOUT_SECONDS
        )

    response.raise_for_status()
    try:
        return response.json()
    except ValueError:
        return {"status_code": response.status_code, "text": response.text}


def record_and_upload(status_callback=None, mock_audio=False, mock_upload=False):
    try:
        _notify_status(status_callback, "listening")
        audio_path = record_audio(mock=mock_audio)
        _notify_status(status_callback, "processing")
        result = upload_audio(audio_path, mock=mock_upload)
        _notify_status(status_callback, "done")
        return result
    except Exception:
        _notify_status(status_callback, "error")
        raise

def start_audio_processing():
    print("Audio Controller Started...")
    while True:
        # Placeholder for audio logic
        time.sleep(10)

if __name__ == "__main__":
    start_audio_processing()
