# main.py
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from core.config import settings
from db.database import engine
from db import models

from api.v1 import files
from api.v1 import health

# 서버 구동 시 DB 테이블 자동 생성 (테이블이 없으면 생성, 있으면 패스)
models.Base.metadata.create_all(bind=engine)

# FastAPI 앱 인스턴스 생성 (config.py의 메타데이터 적용)
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION
)

# WAV 음성 공유 마운트 폴더 생성
os.makedirs("shared_uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="shared_uploads"), name="static")

# 라우터 등록
app.include_router(files.router, prefix="/api/v1/files", tags=["Files"])
app.include_router(health.router, prefix="/api/v1", tags=["System"])

# 사용자 작성 코드 (Root Endpoint)
@app.get("/")
def read_root():
    return {"message": "Welcome to Central API Server"}
