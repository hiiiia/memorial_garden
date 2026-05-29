# backend\app\api\v1\callbacks\jobs.py
from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel
import os

from db.database import get_db 
from db import models
from sqlalchemy.orm import Session
         
router = APIRouter()

# --- 1. Pydantic 스키마 정의 ---
class AnalysisData(BaseModel):
    risk_score: float
    primary_emotion: str
    llm_summary: str
    reply_text: str

class CallbackRequest(BaseModel):
    user_id: str
    status: str
    analysis_data: AnalysisData

# --- 2. 보안 토큰 검증 함수 ---
AI_SECRET_TOKEN = os.getenv("AI_SECRET_TOKEN", "my_super_secret_token") 

async def verify_ai_token(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")
    
    token = authorization.split(" ")[1]
    if token != AI_SECRET_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden: 토큰이 일치하지 않습니다.")
    
    return token



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
        
        # 2. DB 업데이트 (성공 상태 및 분석 데이터 매핑)
        log_record.status = "COMPLETED"
        log_record.risk_score = payload.analysis_data.risk_score
        log_record.primary_emotion = payload.analysis_data.primary_emotion
        log_record.llm_summary = payload.analysis_data.llm_summary
        log_record.reply_text = payload.analysis_data.reply_text
        
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
    
    return {"message": "Callback processed successfully", "job_id": job_id}