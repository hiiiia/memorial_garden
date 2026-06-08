# C:\Users\User\Documents\memorial_garden\backend\app\main.py
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
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

# CORS 미들웨어 설정 (반드시 app.include_router 보다 위에 작성)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # 로컬 React 환경 허용
        "http://172.18.0.2:3000"   # 도커 내부 네트워크 IP도 혹시 모르니 허용
    ],
    allow_credentials=True,
    allow_methods=["*"],           # GET, POST, PUT, DELETE 등 모든 행동 허용
    allow_headers=["*"],           # 모든 헤더 데이터 허용
)


# 라우터 등록 (이 한 줄로 모든 api/v1/... 경로가 활성화됩니다!)
app.include_router(api_router, prefix="/api/v1")

# 사용자 작성 코드 (Root Endpoint)
@app.get("/")
def read_root():
    return {"message": "Welcome to Central API Server"}