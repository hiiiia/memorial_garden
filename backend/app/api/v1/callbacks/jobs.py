# backend\app\api\v1\callbacks\jobs.py
from fastapi import APIRouter, Header, HTTPException, Depends, Request, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
import os
import httpx
import aiofiles
import asyncio
from datetime import datetime
from typing import Optional
import uuid 


from db.database import get_db 
from db import models
from core.config import settings
from api.v1.utils.notifier import send_emergency_alert, send_kakao_alert
from api.v1.utils.security import verify_ai_token
from core.response import unified_response
from api.v1.ws.ws_router import notify_new_diary_to_device

router = APIRouter()

class HealthcareAnalysisData(BaseModel):
    risk_score: float
    primary_emotion: str
    llm_summary: str
    image_url: Optional[str] = None
    diary_text: Optional[str] = None
    depression_score: float
    cognitive_decline_score: float
    care_level: str
    # 음향 바이오마커 추가
    speech_rate: float
    pause_ratio: float
    pitch_variance: float

class LogCreateRequest(BaseModel):
    user_id: str
    status: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    analysis_data: HealthcareAnalysisData

@router.post("/analyze-result", summary="AI 서버 심층 분석 결과 다이렉트 적재")
async def receive_healthcare_log(
    request: LogCreateRequest, 
    req: Request, # 서버의 기본 도메인을 동적으로 가져오기 위해 추가
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    AI 서버가 비동기로 분석을 완료한 헬스케어 데이터를 DB에 저장.
    이미지 URL이 포함되어 있다면 백엔드 서버로 다운로드 후 로컬 URL로 변환하여 적재.
    """
    try:
        if request.status == "FAILED":
            print(f"[Backend] AI 서버 분석 실패 로그 수신: {request.error_message}")
            return {"message": "Failure log received safely."}

        analysis = request.analysis_data
        
        # 1. 이미지 다운로드 및 로컬 URL 변환 로직
        final_image_url = analysis.image_url

        if final_image_url and final_image_url.startswith("http"):
            save_dir = "/app/uploads/diary_images" # 서버 환경에 맞춰 경로 수정
            os.makedirs(save_dir, exist_ok=True)
            
            # 충돌 방지를 위해 UUID로 고유 파일명 생성
            unique_filename = f"diary_{uuid.uuid4().hex}.png"
            save_path = os.path.join(save_dir, unique_filename)
            
            try:
                print(f"[Backend] AI 서버로부터 이미지를 다운로드합니다: {final_image_url}")
                # 비동기로 이미지 다운로드
                async with httpx.AsyncClient(timeout=30.0) as client:
                    img_response = await client.get(final_image_url)
                    img_response.raise_for_status()
                    
                    with open(save_path, "wb") as f:
                        f.write(img_response.content)
                
                # Request 객체를 사용해 현재 백엔드 도메인을 동적으로 획득 (예: http://localhost:8000)
                base_url = str(req.base_url).rstrip("/")
                final_image_url = f"{base_url}/static/diary_images/{unique_filename}"
                print(f"[Backend] 로컬 저장 완료. DB 적재 URL: {final_image_url}")
                
            except Exception as img_err:
                print(f"[Backend Error] 이미지 다운로드 실패 (원본 URL 유지): {img_err}")
                # 실패하면 원본 URL을 그대로 유지하도록 처리
                
        # 2. Log 테이블에 새 레코드 생성
        new_log = models.Log(
            dependent_id=request.user_id,
            status=request.status,
            risk_score=analysis.risk_score,
            depression_score=analysis.depression_score,
            cognitive_decline_score=analysis.cognitive_decline_score,
            primary_emotion=analysis.primary_emotion,
            llm_summary=analysis.llm_summary,
            image_url=final_image_url, 
            diary_text=analysis.diary_text,
            speech_rate=analysis.speech_rate,
            pause_ratio=analysis.pause_ratio,
            pitch_variance=analysis.pitch_variance
        )
        
        try:
            db.add(new_log)
            db.flush()

            print(f"[Backend] 새로운 헬스케어 로그 (Log ID: {new_log.id})")
            
            # ====================================================
            # 🚨 위험도 평가, Alert DB 기록 및 보호자 알림 발송
            # ====================================================
            DANGER_THRESHOLD = 70.0
            
            # 1) Alert 테이블에 상태 기록 (위험하면 PENDING, 정상이면 RESOLVED)
            trigger_type = "AI_RISK" if analysis.risk_score >= DANGER_THRESHOLD else "INFO"
            
            new_alert = models.Alert(
                dependent_id=request.user_id,
                log_id=new_log.id,
                trigger_type=trigger_type,
                status="RESOLVED" if trigger_type == "INFO" else "PENDING"
            )
            
            db.commit() 
            db.refresh(new_log)
            
            print(f"[Backend] 새로운 헬스케어 로그 및 Alert 적재 완료 (Log ID: {new_log.id})")
            
            # 2) 위험 기준치 초과 시 외부 알림 발송
            if analysis.risk_score >= DANGER_THRESHOLD:
                # 연결된 보호자 조회
                connected_mappings = db.query(models.GuardianDependentMapping).filter(
                    models.GuardianDependentMapping.dependent_id == request.user_id,
                    models.GuardianDependentMapping.status == "CONNECTED"
                ).all()
                
                for mapping in connected_mappings:
                    guardian_obj = mapping.guardian
                    # 어르신 이름 가져오기 (관계 매핑에 dependent가 연결되어 있다고 가정)
                    target_name = mapping.dependent.name if hasattr(mapping, 'dependent') and mapping.dependent else "어르신"
                    
                    print(f"[Alert] 위험 감지! {guardian_obj.name} 보호자에게 알림 발송 예약.")
                    
                    # 🌟 응답 지연이 없도록 FastAPI background_tasks로 외부 통신 넘기기
                    background_tasks.add_task(
                        send_emergency_alert,
                        risk_score=analysis.risk_score,
                        summary=analysis.llm_summary,
                        text=analysis.diary_text, # 레거시의 stt_text 대신 현재 사용중인 diary_text로 교체
                        dependent_name=target_name,
                        guardian_phone=guardian_obj.phone,
                        guardian_name=guardian_obj.name
                    )
                    background_tasks.add_task(
                        send_kakao_alert,
                        guardian=guardian_obj,
                        dependent_name=target_name,
                        risk_score=analysis.risk_score,
                        summary=analysis.llm_summary
                    )
            # ====================================================

            # 기존: 어르신 기기(프론트엔드)로 새 일기 도착 웹소켓 알림
            background_tasks.add_task(
                notify_new_diary_to_device,
                request.user_id,
                new_log
            )
            
            return {"message": "Log successfully saved.", "log_id": new_log.id}
            
        except Exception as e:
            db.rollback()
            print(f"[Backend Error] 로그 저장 중 DB 오류 발생: {e}")
            raise HTTPException(status_code=500, detail="Database insertion failed.")

    except Exception as e:
        db.rollback()
        print(f"[Backend Error] 로그 저장 중 DB 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="Database insertion failed.")
