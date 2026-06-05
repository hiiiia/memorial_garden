# C:\Users\User\Documents\memorial_garden\backend\app\main.py
import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from core.config import settings
from db.database import engine
from db import models
from sqlalchemy.exc import OperationalError

from core.response import unified_response
from api.v1.router import api_router 

try:
    # 서버 구동 시 DB 테이블 자동 생성
    models.Base.metadata.create_all(bind=engine)
except OperationalError as e:
    # DB가 꺼져있어도 FastAPI 서버 자체는 일단 켜지도록 예외 처리
    print(f"⚠️ [경고] 서버 구동 중 DB 연결에 실패했습니다: {e}")
    
    
# FastAPI 앱 인스턴스 생성
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION
)

# API 통신(요청) 중 발생하는 DB 연결 에러 방어 (Global Exception Handler)
@app.exception_handler(OperationalError)
async def db_operational_error_handler(request: Request, exc: OperationalError):
    print(f"🚨 데이터베이스 연결 오류 발생: {exc}") # 서버 콘솔용 로그
    return unified_response(
        status_code=503, # 503 Service Unavailable
        message="데이터베이스 서버와 연결할 수 없습니다. (Timeout)",
        data={"detail": str(exc)}
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