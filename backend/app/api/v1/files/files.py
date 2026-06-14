import httpx
import os
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, Form, status, BackgroundTasks, Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from core.config import settings
from core.storage import save_file_and_get_url
from core.response import unified_response
from db.database import get_db, SessionLocal
from db import models
from api.v1.utils.memory_profile import build_memory_profile_context

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
    user_id: str = Form(..., description="어르신 고유 ID"),
    device_id: str = Form(...),
    audio_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    new_job_id = uuid.uuid4().hex
    
    # 1. 시크릿 토큰 검증 (HTTPBearer)
    if not credentials or credentials.scheme != "Bearer" or credentials.credentials != settings.API_SECRET_TOKEN:
        print("인증 실패: 토큰 누락 또는 불일치")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized. Invalid or missing token."
        )

    # 2. 유효한 대상자인지 DB 검증 (방어선 구축)
    dependent_exists = db.query(models.Dependent).filter(models.Dependent.id == user_id).first()
    if not dependent_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Failed. Target dependent user not found."
        )

    # 3. 파일 확장자 검증 (오디오 포맷 체크)
    if not audio_file.filename.endswith(('.wav', '.mp3', '.m4a')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed. Invalid file format."
        )
    
    # 4. 파일 저장소 스토리지 업로드 및 오디오 파일 URL 획득 
    try:
        real_file_url = await save_file_and_get_url(audio_file, request)
    except Exception as e:
        print(f"파일 저장 에러: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File Save Error"
        )

    # 5. DB 로그 생성 (기록 저장)
    try:
        new_log = models.Log(
            id=new_job_id,
            dependent_id=user_id,
            file_url=real_file_url,
            image_url=None,          # [DB 스펙 반영] 초기 업로드 시에는 그림일기가 없으므로 명시적 null 세팅
            status="PROCESSING"
        )
        db.add(new_log)
        db.commit()
    except Exception as e: 
        print(f"[DB 저장 에러 발생]: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed. Check Data"
        )

    # 성공 응답 규격 생성 및 구조화 전송
    return unified_response(
        status_code=status.HTTP_201_CREATED,
        message="File uploaded successful.",
        data={
            "file_url": real_file_url,
            "job_id" : new_job_id
        }
    )


# ----------------------------------------------------
# [스펙 2] 데이터 분석 요청 (백그라운드 비동기 인계 구조)
# 스펙: POST /api/v1/files/analysis/jobs
# ----------------------------------------------------

class AnalysisJobRequest(BaseModel):
    user_id: str
    device_id: str
    file_url: str
    job_id: str

def get_memory_profile_context(user_id: str):
    db = SessionLocal()
    try:
        return build_memory_profile_context(db, user_id)
    except Exception as e:
        print(f"[Backend] 장기기억 프로필 조회 실패: {str(e)}")
        return []
    finally:
        db.close()

# AI 서버로 분석 요청을 파이프라이닝하는 비동기 워커 태스크
async def forward_to_ai_server(payload: dict):
    ai_target_url = f"{settings.AI_PROXY_URL}/api/v1/analyze"
    callback_url = f"http://backend:8000/api/v1/callbacks/jobs/{payload['job_id']}/analyzing-result"
    memory_profile_context = get_memory_profile_context(payload["user_id"])

    async with httpx.AsyncClient() as client:
        try:
            print(f"[Backend] AI 서버로 분석 요청 송신 중... (Job ID: {payload['job_id']})")
            
            response = await client.post(
                ai_target_url,
                json={
                    "job_id": payload["job_id"], 
                    "user_id": payload["user_id"], 
                    "file_path": payload["file_url"], 
                    "callback_url": callback_url,
                    "memory_profile_context": memory_profile_context
                },
                headers={
                    "Authorization": f"Bearer {settings.AI_SECRET_TOKEN}", 
                    "Content-Type": "application/json"
                },
                timeout=10.0
            )
            response.raise_for_status()
            print(f"[AI 인계 성공] Status: {response.status_code}, Job ID: {payload['job_id']}")
            
        except Exception as e:
            print(f"[AI 인계 실패] 에러 발생: {str(e)}")
            
            # 네트워크 통신 장애 혹은 프록시 타임아웃 발생 시 FAILED 상태 트래킹 진행
            db = SessionLocal()
            try:
                log_record = db.query(models.Log).filter(models.Log.id == payload['job_id']).first()
                if log_record:
                    log_record.status = "FAILED"
                    db.commit()
            except Exception as db_e:
                print(f"[DB 롤백 오류] 상태 업데이트 실패: {str(db_e)}")
                db.rollback()
            finally:
                db.close()


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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized. Invalid or missing token."
        )
        
    try:
        # 2.  검사 및 로그 덮어쓰기 로직
        log_record = db.query(models.Log).filter(models.Log.id == request_data.job_id).first()
        
        if log_record:
            log_record.file_url = request_data.file_url
            log_record.status = "PROCESSING"
        else:
            log_record = models.Log(
                id=request_data.job_id,
                dependent_id=request_data.user_id,
                file_url=request_data.file_url,
                image_url=None,  # [DB 스펙 반영] 신규 로그 등록 시 초기값 세팅 보장
                status="PROCESSING"
            )
            db.add(log_record)
            
        db.commit()
    except Exception as e:
        print(f"DB 처리 중 에러 발생: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed. Check Format"
        )

    # 3. 비동기 백그라운드 스케줄러 적재
    background_tasks.add_task(forward_to_ai_server, request_data.dict())

    # 4. Success 비동기 인계 접수 완료 반환
    return unified_response(
        status_code=status.HTTP_202_ACCEPTED,
        message="Log and analysis Queued.",
        data={"job_id": request_data.job_id}
    )
