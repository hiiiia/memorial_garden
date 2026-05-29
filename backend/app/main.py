# C:\Users\User\Documents\memorial_garden\backend\app\main.py
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from core.config import settings
from db.database import engine
from db import models

from api.v1.router import api_router 

# 서버 구동 시 DB 테이블 자동 생성
models.Base.metadata.create_all(bind=engine)

# FastAPI 앱 인스턴스 생성
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION
)

# WAV 음성 공유 마운트 폴더 생성
os.makedirs("shared_uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="shared_uploads"), name="static")

# 라우터 등록 (이 한 줄로 모든 api/v1/... 경로가 활성화됩니다!)
app.include_router(api_router, prefix="/api/v1")

# 사용자 작성 코드 (Root Endpoint)
@app.get("/")
def read_root():
    return {"message": "Welcome to Central API Server"}