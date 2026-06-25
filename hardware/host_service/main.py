from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import NoReturn

from dotenv import load_dotenv


SERVICE_DIR = Path(__file__).resolve().parent
load_dotenv(SERVICE_DIR / ".env")

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from audio_controller import (
    AudioConflictError,
    AudioController,
    AudioControllerError,
    AudioFileNotFoundError,
    AudioPathNotAllowedError,
    AudioUnavailableError,
    InvalidRecordingError,
)


logging.basicConfig(
    level=getattr(logging, os.getenv("HARDWARE_LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("hardware_service")


def _cors_origins() -> list[str]:
    default_origins = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:3001,http://127.0.0.1:3001,"
        "http://localhost:5173,http://127.0.0.1:5173"
    )
    raw_origins = os.getenv("HARDWARE_CORS_ORIGINS", default_origins)
    origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    return origins or ["http://localhost:3001"]


audio_controller = AudioController()


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Raspberry Pi 하드웨어 제어 서버를 시작합니다.")
    health = audio_controller.health()
    if health["status"] == "degraded":
        logger.warning("오디오 장치가 준비되지 않은 상태로 서버를 시작합니다: %s", health)
    try:
        yield
    finally:
        audio_controller.shutdown()
        logger.info("Raspberry Pi 하드웨어 제어 서버를 종료했습니다.")


app = FastAPI(
    title="Memorial Garden Raspberry Pi Hardware API",
    version="1.0.0",
    lifespan=lifespan,
)

allowed_origins = _cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class PlayAudioRequest(BaseModel):
    path: str = Field(..., min_length=1, description="재생할 로컬 WAV 파일 경로")


def _raise_http_error(error: AudioControllerError) -> NoReturn:
    if isinstance(error, AudioConflictError):
        status_code = 409
    elif isinstance(error, AudioUnavailableError):
        status_code = 503
    elif isinstance(error, AudioFileNotFoundError):
        status_code = 404
    elif isinstance(error, AudioPathNotAllowedError):
        status_code = 400
    elif isinstance(error, InvalidRecordingError):
        status_code = 500
    else:
        status_code = 500
    raise HTTPException(status_code=status_code, detail=str(error)) from error


@app.get("/health")
def health() -> dict[str, object]:
    return audio_controller.health()


@app.get("/hardware/status")
def hardware_status() -> dict[str, object]:
    return audio_controller.status()


@app.post("/hardware/record/start")
def start_recording() -> dict[str, object]:
    try:
        return audio_controller.start_recording()
    except AudioControllerError as error:
        _raise_http_error(error)


@app.post("/hardware/record/stop")
def stop_recording() -> dict[str, object]:
    try:
        return audio_controller.stop_recording()
    except AudioControllerError as error:
        _raise_http_error(error)


@app.post("/hardware/audio/play")
def play_audio(request: PlayAudioRequest) -> dict[str, object]:
    try:
        return audio_controller.play(request.path)
    except AudioControllerError as error:
        _raise_http_error(error)


@app.post("/hardware/audio/stop")
def stop_audio() -> dict[str, object]:
    try:
        return audio_controller.stop_playback()
    except AudioControllerError as error:
        _raise_http_error(error)


@app.get("/hardware/recordings")
def recordings(
    limit: int = Query(default=20, ge=1, le=200),
) -> dict[str, object]:
    try:
        items = audio_controller.list_recordings(limit=limit)
    except AudioControllerError as error:
        _raise_http_error(error)
    return {"count": len(items), "recordings": items}


def _hardware_port() -> int:
    raw_port = os.getenv("HARDWARE_PORT", "8002")
    try:
        return int(raw_port)
    except ValueError:
        logger.warning("잘못된 HARDWARE_PORT=%r, 기본값 8002를 사용합니다.", raw_port)
        return 8002


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=_hardware_port(), reload=False)
