# api/v1/files.py
import httpx
import os
from fastapi import APIRouter, Depends, UploadFile, File, Form, status, BackgroundTasks, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

from core.config import settings
from core.storage import save_file_and_get_url
from core.response import unified_response
from db.database import get_db
from db import models

router = APIRouter()

# Bearer 토큰 인증 객체 생성
security = HTTPBearer(auto_error=False)

# ----------------------------------------------------
# [스펙 1] 음성 데이터 업로드
# 스펙: POST /api/v1/files/audio
# ----------------------------------------------------
@router.post("/audio", status_code=status.HTTP_201_CREATED)
async def upload_audio(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user_id: str = Form(...),
    device_id: str = Form(...),
    audio_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # 1. 검증 로직
    # 인증 실패 응답 (401 일괄 적용)
    if not credentials or credentials.scheme != "Bearer" or credentials.credentials != settings.API_SECRET_TOKEN:
        print("인증 실패: 토큰 누락 또는 불일치")
        return unified_response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error="Unauthorized. Invalid or missing token."
        )

    # 2. 파일 확장자 검증 (400 일괄 적용)
    if not audio_file.filename.endswith(('.wav', '.mp3', '.m4a')):
        return unified_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            error="Failed. Check Data"
        )
    
    # 3. 파일 저장 및 URL 획득 
    try:
        real_file_url = await save_file_and_get_url(audio_file, request)
    except Exception as e:
        print(f"파일 저장 에러: {e}")
        return unified_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="File Save Error"
        )

    # 4. DB 저장
    try:
        new_log = models.Log(
            dependent_id=user_id,
            file_url=real_file_url,
            status="PROCESSING"
        )
        db.add(new_log)
        db.commit()
    except Exception as e: 
        print(f"[DB 저장 에러 발생]: {e}")
        db.rollback()
        return unified_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            error="Failed. Check Data"
        )

    # 성공 응답 (201 일괄 적용 - URL은 data 필드에 주입)
    return unified_response(
        status_code=status.HTTP_201_CREATED,
        message="File uploaded successful.",
        data={"file_url": real_file_url}
    )


# ----------------------------------------------------
# [스펙 2] 데이터 분석 요청 (백그라운드 비동기 인계 구조)
# 스펙: POST /api/v1/files/analysis/jobs
# ----------------------------------------------------

# 명세서의 Request Body JSON 스펙 정의
class AnalysisJobRequest(BaseModel):
    user_id: str
    device_id: str
    data_type: str
    file_url: str
    recorded_at: str
    job_id: str


# AI 분석 서버로 작업을 비동기 인계하는 내부 함수
async def forward_to_ai_server(payload: dict):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{settings.AI_PROXY_URL}/api/v1/analyze", 
                json={
                    "file_url": payload["file_url"],
                    "callback_url": f"http://backend:8000/api/v1/callbacks/jobs/{payload['job_id']}/analyzing-result"
                },
                timeout=10.0
            )
            print(f"[AI 인계 완료] Status: {response.status_code}, Job ID: {payload['job_id']}")
        except Exception as e:
            print(f"[AI 인계 실패] 에러 발생: {str(e)}")


@router.post("/analysis/jobs", status_code=status.HTTP_202_ACCEPTED)
async def request_analysis(
    background_tasks: BackgroundTasks,
    request_data: AnalysisJobRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    # 1. Header 토큰 검증
    if not credentials or credentials.scheme != "Bearer" or credentials.credentials != settings.API_SECRET_TOKEN:
        print("인증 실패: 토큰 누락 또는 불일치")
        return unified_response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error="Unauthorized. Invalid or missing token."
        )
        
    try:
        # 2. 명세서로 들어온 job_id가 이미 존재하는지 로그 확인 후 업데이트 혹은 신규 등록
        log_record = db.query(models.Log).filter(models.Log.id == request_data.job_id).first()
        
        if log_record:
            log_record.file_url = request_data.file_url
            log_record.status = "PROCESSING"
        else:
            log_record = models.Log(
                id=request_data.job_id,
                dependent_id=request_data.user_id,
                file_url=request_data.file_url,
                status="PROCESSING"
            )
            db.add(log_record)
            
        db.commit()
    except Exception as e:
        print(f"DB 처리 중 에러 발생: {e}")
        db.rollback()
        return unified_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            error="Failed. Check Format"
        )

    # 3. 백그라운드 태스크 등록
    background_tasks.add_task(forward_to_ai_server, request_data.dict())

    # 4. Success 응답 (202 일괄 적용 - job_id는 data 필드에 주입)
    return unified_response(
        status_code=status.HTTP_202_ACCEPTED,
        message="Log and analysis Queued.",
        data={"job_id": request_data.job_id}
    )