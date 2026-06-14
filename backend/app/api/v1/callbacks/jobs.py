# backend\app\api\v1\callbacks\jobs.py
from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import os
import httpx
import aiofiles
import asyncio
from datetime import datetime
from typing import List, Optional

# openAPI TTS 사용시 edge-tts는 주석처리
import edge_tts

from db.database import get_db 
from db import models
from core.config import settings
from api.v1.utils.notifier import send_emergency_alert, send_kakao_alert
from api.v1.utils.security import verify_ai_token
from api.v1.utils.memory_profile import save_memory_analysis

router = APIRouter()

# --- 1. Pydantic 스키마 정의 ---
class MemoryProfileUpdate(BaseModel):
    category: str
    key: str
    value: str
    confidence: float = 0.0
    source_text: Optional[str] = None
    importance: str = "MEDIUM"

class MemoryConflictItem(BaseModel):
    category: str
    key: str
    previous_value: str
    current_value: str
    source_text: Optional[str] = None
    severity: str = "WATCH"
    note: Optional[str] = None

class AnalysisData(BaseModel):
    risk_score: float = 0.0
    primary_emotion: str = "neutral"
    llm_summary: str = ""
    reply_text: str = ""
    stt_text : str = ""
    image_url: Optional[str] = None # AI가 생성한 그림일기 URL 추가
    depression_score: float = 0.0
    cognitive_decline_score: float = 0.0
    care_level: str = "NORMAL"
    diary_text: str = ""
    memory_profile_updates: List[MemoryProfileUpdate] = Field(default_factory=list)
    memory_conflicts: List[MemoryConflictItem] = Field(default_factory=list)

class CallbackRequest(BaseModel):
    user_id: str
    status: str
    analysis_data: AnalysisData

# --- 2. 보안 토큰 검증 함수 ---
AI_SECRET_TOKEN = settings.AI_SECRET_TOKEN
OPENAI_API_KEY = settings.OPENAI_API_KEY


# async def generate_tts_audio_open_ai(text: str, job_id: str) -> str:
#     """OpenAI TTS를 호출하여 음성 파일을 생성하고 경로를 반환합니다."""
    
#     # 저장할 파일명과 경로 세팅 (기존에 세팅하신 shared_uploads 폴더 활용)
#     file_name = f"reply_{job_id}.mp3"
#     save_path = os.path.join("shared_uploads", file_name)
#     static_url = f"http://localhost:8000/static/{file_name}" # 스피커가 접근할 URL
    
#     url = "https://api.openai.com/v1/audio/speech"
#     headers = {
#         "Authorization": f"Bearer {OPENAI_API_KEY}",
#         "Content-Type": "application/json"
#     }
#     data = {
#         "model": "tts-1",
#         "input": text,
#         "voice": "nova", # nova: 다정하고 상냥한 여성 톤 / alloy: 중성적 톤 / onyx: 남성 톤
#         "response_format": "mp3" 
#     }
    
#     print(f"[TTS] 🎙️ 음성 생성 요청 중... (Text: {text[:15]}...)")
    
#     async with httpx.AsyncClient() as client:
#         response = await client.post(url, headers=headers, json=data, timeout=30.0)
        
#         if response.status_code == 200:
#             # 스트리밍으로 받아서 파일로 저장 (aiofiles 사용)
#             async with aiofiles.open(save_path, 'wb') as f:
#                 await f.write(response.content)
#             print(f"[TTS] ✅ 음성 파일 생성 완료: {save_path}")
#             return static_url
#         else:
#             print(f"[TTS Error] 음성 생성 실패: {response.text}")
#             return None

async def generate_tts_audio_edge(text: str, job_id: str) -> str:
    """Edge-TTS를 사용하여 무료로 고음질 음성을 생성합니다."""
    # 1. 오늘 날짜로 폴더 경로 만들기 (예: shared_uploads/20260529)
    today_str = datetime.now().strftime("%Y%m%d")
    base_dir = os.path.join("shared_uploads", today_str)
    
    # 폴더가 없으면 자동으로 생성
    os.makedirs(base_dir, exist_ok=True)
    
    # 2. 최종 저장 경로와 URL 세팅
    file_name = f"reply_{job_id}.mp3"
    save_path = os.path.join(base_dir, file_name) # shared_uploads/20260529/reply_...mp3
    static_url = f"http://localhost:8000/static/{today_str}/{file_name}"
    
    voice = "ko-KR-SunHiNeural"
    
    print(f"[TTS] 🎙️ 무료 음성 생성 요청 중... (Text: {text[:15]}...)")
    
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(save_path)
        
        print(f"[TTS] ✅ 무료 음성 파일 생성 완료: {save_path}")
        return static_url
    except Exception as e:
        print(f"[TTS Error] 음성 생성 실패: {e}")
        return None


# --- 3. 콜백 API 엔드포인트 ---
@router.post("/{job_id}/analyzing-result")
async def receive_ai_callback(
    job_id: str, 
    payload: CallbackRequest, 
    token: str = Depends(verify_ai_token),
    db: Session = Depends(get_db)
):
    print(f"\n[Backend] 🔔 AI 서버로부터 콜백 수신 완료! (Job ID: {job_id})")
    
    # 1. DB에서 해당 job_id 찾기
    log_record = db.query(models.Log).filter(models.Log.id == job_id).first()
    
    if not log_record:
        print(f"[Backend Error] DB에서 해당 Job ID({job_id})를 찾을 수 없습니다.")
        raise HTTPException(status_code=404, detail="Job ID not found")
    
    if payload.status == "COMPLETED":
        # 2. DB 업데이트 (분석 데이터 매핑 및 그림일기 URL 추가)
        log_record.status = "COMPLETED"
        log_record.risk_score = payload.analysis_data.risk_score
        log_record.primary_emotion = payload.analysis_data.primary_emotion
        log_record.llm_summary = payload.analysis_data.llm_summary
        log_record.reply_text = payload.analysis_data.reply_text
        log_record.stt_text = payload.analysis_data.stt_text
        log_record.depression_score = payload.analysis_data.depression_score
        log_record.cognitive_decline_score = payload.analysis_data.cognitive_decline_score
        log_record.diary_text = payload.analysis_data.diary_text or payload.analysis_data.llm_summary
        save_memory_analysis(
            db=db,
            user_id=payload.user_id,
            updates=payload.analysis_data.memory_profile_updates,
            conflicts=payload.analysis_data.memory_conflicts
        )
        print(
            "[Backend] memory_profile_updates="
            f"{len(payload.analysis_data.memory_profile_updates)}, "
            f"memory_conflicts={len(payload.analysis_data.memory_conflicts)}"
        )
        
        # 그림일기 이미지가 생성되어 넘어왔다면 저장
        if payload.analysis_data.image_url:
            log_record.image_url = payload.analysis_data.image_url
            
        # TTS 생성 및 파일 경로 저장
        if payload.analysis_data.reply_text:
            audio_url = await generate_tts_audio_edge(payload.analysis_data.reply_text, job_id)
            if audio_url:
                log_record.reply_audio_url = audio_url 
                
    elif payload.status == "FAILED":
        print("[Backend] 🚨 AI 분석 실패 보고를 받았습니다.")
        log_record.status = "FAILED"
        
    # 3. 트랜잭션 확정 (DB에 영구 저장)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[Backend Error] DB 커밋 중 에러 발생: {e}")
        raise HTTPException(status_code=500, detail="Database commit failed")
    
    # 4. 위험도 평가 및 알림 발송 로직
    DANGER_THRESHOLD = 70.0 # 프론트엔드 위험 기준(70점)에 맞춤
        
    if payload.status == "COMPLETED":
        dependent = log_record.dependent
        target_name = dependent.name if dependent else "어르신"
        
        #  매핑 테이블을 통해 현재 'CONNECTED' 상태인 모든 보호자 찾기
        connected_mappings = db.query(models.GuardianDependentMapping).filter(
            models.GuardianDependentMapping.dependent_id == log_record.dependent_id,
            models.GuardianDependentMapping.status == "CONNECTED"
        ).all()

        # 대시보드 위젯에 띄워줄 알림을 DB(Alert 테이블)에 저장
        trigger_type = "AI_RISK" if payload.analysis_data.risk_score >= DANGER_THRESHOLD else "INFO"
        
        new_alert = models.Alert(
            dependent_id=log_record.dependent_id,
            log_id=log_record.id,
            trigger_type=trigger_type,
            status="RESOLVED" if trigger_type == "INFO" else "PENDING"
        )
        db.add(new_alert)
        db.commit()
        
        # 위험 수치를 넘었을 때만 외부 메신저(카톡/슬랙) 알림 발송
        if payload.analysis_data.risk_score >= DANGER_THRESHOLD:
            for mapping in connected_mappings:
                guardian_obj = mapping.guardian
                print(f"[Alert] 위험 감지! {guardian_obj.name} 보호자에게 알림을 발송합니다.")
                
                await asyncio.gather(
                    send_emergency_alert(
                        risk_score=payload.analysis_data.risk_score,
                        summary=payload.analysis_data.llm_summary,
                        text=payload.analysis_data.stt_text,
                        dependent_name=target_name,
                        guardian_phone=guardian_obj.phone,
                        guardian_name=guardian_obj.name
                    ),
                    send_kakao_alert(
                        guardian=guardian_obj,
                        dependent_name=target_name,
                        risk_score=payload.analysis_data.risk_score,
                        summary=payload.analysis_data.llm_summary
                    )
                )

    return {"message": "Callback processed successfully", "job_id": job_id}
