# backend\app\api\v1\callbacks\jobs.py
from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
import os
import httpx
import aiofiles
from datetime import datetime

# openAPI TTS 사용시 edge-tts는 주석처리
import edge_tts

from db.database import get_db 
from db import models
from core.config import settings
from api.v1.utils.notifier import send_emergency_alert


router = APIRouter()

# --- 1. Pydantic 스키마 정의 ---
class AnalysisData(BaseModel):
    risk_score: float
    primary_emotion: str
    llm_summary: str
    reply_text: str
    stt_text : str

class CallbackRequest(BaseModel):
    user_id: str
    status: str
    analysis_data: AnalysisData

# --- 2. 보안 토큰 검증 함수 ---
AI_SECRET_TOKEN = settings.AI_SECRET_TOKEN
OPENAI_API_KEY = settings.OPENAI_API_KEY

async def verify_ai_token(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")
    
    token = authorization.split(" ")[1]
    if token != AI_SECRET_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden: 토큰이 일치하지 않습니다.")
    
    return token

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
#             # 🌟 스트리밍으로 받아서 파일로 저장 (aiofiles 사용)
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
    print(f"[Backend] 상태: {payload.status}")
    
    # 1. DB에서 해당 job_id 찾기
    log_record = db.query(models.Log).filter(models.Log.id == job_id).first()
    
    if not log_record:
        print(f"[Backend Error] DB에서 해당 Job ID({job_id})를 찾을 수 없습니다.")
        raise HTTPException(status_code=404, detail="Job ID not found")
    
    if payload.status == "COMPLETED":
        
        
        print(f"[Backend] 위험도: {payload.analysis_data.risk_score}")
        print(f"[Backend] 주 감정: {payload.analysis_data.primary_emotion}")
        print(f"[Backend] AI 요약: {payload.analysis_data.llm_summary}")
        print(f"[Backend] 💬 AI 답변: {payload.analysis_data.reply_text}")
        print(f"[Backend] 💬 STT: {payload.analysis_data.stt_text}")
        
        # 2. DB 업데이트 (성공 상태 및 분석 데이터 매핑)
        log_record.status = "COMPLETED"
        log_record.risk_score = payload.analysis_data.risk_score
        log_record.primary_emotion = payload.analysis_data.primary_emotion
        log_record.llm_summary = payload.analysis_data.llm_summary
        log_record.reply_text = payload.analysis_data.reply_text
        log_record.stt_text = payload.analysis_data.stt_text
        
        # TTS 생성 및 파일 경로 저장
        if payload.analysis_data.reply_text:
            audio_url = await generate_tts_audio_edge(payload.analysis_data.reply_text, job_id)
            if audio_url:
                log_record.reply_audio_url = audio_url # DB에 음성 파일 URL 업데이트
                
    elif payload.status == "FAILED":
        print("[Backend] 🚨 AI 분석 실패 보고를 받았습니다.")
        
        # 3. DB 업데이트 (실패 상태만 변경)
        log_record.status = "FAILED"
        
    # 4. 트랜잭션 확정 (DB에 영구 저장)
    try:
        db.commit()
        print("[Backend] ✅ DB 업데이트 및 커밋 완료!")
    except Exception as e:
        db.rollback()
        print(f"[Backend Error] DB 커밋 중 에러 발생: {e}")
        raise HTTPException(status_code=500, detail="Database commit failed")
    
    
    DANGER_THRESHOLD = 0.0
        
    if payload.analysis_data.risk_score >= DANGER_THRESHOLD:
        # 백그라운드로 알림
        target_name = log_record.dependent.name if log_record.dependent else "알 수 없는 사용자"
        await send_emergency_alert(
            risk_score=payload.analysis_data.risk_score,
            summary=payload.analysis_data.llm_summary,
            text=payload.analysis_data.stt_text, # (원래는 STT 텍스트 원본이 들어가야 좋습니다)
            
            dependent_name = target_name, # 어르신
            guardian_phone = log_record.dependent.guardian.phone, # 보호자 전화번호 (알림톡 발송용)
            guardian_name = log_record.dependent.guardian.name # 보호
        )
    
    
    return {"message": "Callback processed successfully", "job_id": job_id}