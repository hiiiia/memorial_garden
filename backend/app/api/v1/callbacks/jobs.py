# C:\Users\User\Documents\memorial_garden\backend\app\api\v1\callbacks\jobs.py
from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel
import os

router = APIRouter()

# --- 1. Pydantic 스키마 정의 ---
class AnalysisData(BaseModel):
    risk_score: float
    primary_emotion: str
    llm_summary: str

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
    token: str = Depends(verify_ai_token)
):
    print(f"\n[Backend] 🔔 AI 서버로부터 콜백 수신 완료! (Job ID: {job_id})")
    print(f"[Backend] 상태: {payload.status}")
    
    if payload.status == "COMPLETED":
        print(f"[Backend] 위험도: {payload.analysis_data.risk_score}")
        print(f"[Backend] 주 감정: {payload.analysis_data.primary_emotion}")
        print(f"[Backend] AI 요약: {payload.analysis_data.llm_summary}")
        
        # TODO: DB 저장 로직 추가
        
    elif payload.status == "FAILED":
        print("[Backend] 🚨 AI 분석 실패 보고를 받았습니다.")
        # TODO: DB 실패 상태 변경 로직 추가
        
    return {"message": "Callback processed successfully", "job_id": job_id}