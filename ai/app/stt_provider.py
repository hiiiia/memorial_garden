import asyncio
from pathlib import Path
from typing import Optional

from app.config import settings


STT_MODEL = "gemini-3.5-flash"
STT_PROMPT = (
    "이 오디오 파일에서 사용자가 실제로 말한 한국어 발화만 그대로 텍스트로 적어주세요. "
    "요약, 설명, 추측, 괄호, 접두사는 추가하지 마세요. "
    "인식할 수 있는 말이 없으면 빈 문자열만 반환하세요."
)


class STTError(RuntimeError):
    """WAV 파일에서 실제 발화를 인식하지 못했을 때 발생합니다."""


def _extract_response_text(response) -> str:
    return (getattr(response, "text", "") or "").strip()


def transcribe_wav_sync(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise STTError(f"audio file not found: {file_path}")

    try:
        from google import genai

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        audio_file = client.files.upload(file=str(path))
        response = client.models.generate_content(
            model=STT_MODEL,
            contents=[audio_file, STT_PROMPT],
        )
    except Exception as exc:
        raise STTError(f"STT provider failed: {exc}") from exc

    transcript = _extract_response_text(response)
    if not transcript:
        raise STTError("empty transcript")
    return transcript


async def transcribe_wav(file_path: str) -> str:
    return await asyncio.to_thread(transcribe_wav_sync, file_path)


async def ensure_stt_text(file_path: str, stt_text: Optional[str]) -> str:
    transcript = (stt_text or "").strip()
    if transcript:
        return transcript
    return await transcribe_wav(file_path)
