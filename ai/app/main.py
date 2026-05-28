from fastapi import FastAPI, BackgroundTasks, HTTPException, status, Header, Depends # 🌟 Header, Depends 추가
from pydantic import BaseModel
import httpx
import os
import json

from google import genai
from google.genai import types

from app.config import settings

app = FastAPI()

# ==========================================
# 1. 환경 변수 및 최신 Gemini 클라이언트 설정
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
AI_SECRET_TOKEN = os.getenv("AI_SECRET_TOKEN", "my_super_secret_ai_token")

# 새로운 Client 방식 초기화
client = genai.Client(api_key=settings.GEMINI_API_KEY)

# ==========================================
# 2. 데이터 스키마 및 보안 의존성 정의
# ==========================================
class AnalysisTriggerRequest(BaseModel):
    job_id: str
    user_id: str
    file_path: str  
    callback_url: str 
    
# 토큰 검증 함수
def verify_api_token(authorization: str = Header(None)):
    """
    들어오는 요청의 Header에서 Authorization 토큰을 검사합니다.
    """
    
    print(f"[보안 검사] 백엔드가 보낸 헤더: {authorization}")
    print(f"[보안 검사] AI 서버가 아는 토큰: {AI_SECRET_TOKEN}")
    
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized. Missing token.")
    
    scheme, _, token = authorization.partition(" ")
    
    # settings.AI_SECRET_TOKEN 으로 비교
    if scheme.lower() != "bearer" or token != settings.AI_SECRET_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized. Invalid token.")
    return token



# ==========================================
# 3. 핵심 로직: Gemini 분석 및 백엔드 콜백 전송
# ==========================================
async def process_audio_and_callback(job_id: str, user_id: str, file_path: str, callback_url: str):
    try:
        if not os.path.exists(file_path):
            print(f"[AI Error] 파일을 찾을 수 없습니다: {file_path}")
            return

        print(f"[AI] Gemini 오디오 업로드 시작: {file_path}")
        
        audio_file = client.files.upload(file=file_path)
        
        prompt = """
        이 음성 파일(WAV)을 분석하여 사용자의 자해/위험 징후 및 심리 상태를 평가해주세요.
        반드시 지정된 JSON 포맷으로만 응답해야 하며, 어떠한 마크다운 태그나 설명도 포함하지 마세요.
        
        {
          "risk_score": 0.0에서 1.0 사이의 실수 (위험도가 높고 비극적인 징후일수록 1.0에 가까움),
          "primary_emotion": "happy", "sad", "angry", "anxious", "neutral" 중 하나를 영어 소문자로 선택,
          "llm_summary": "한 줄로 작성된 한국어 심리 상태 요약문"
        }
        """
        
        print("[AI] Gemini 1.5 Flash 분석 요청 중...")
        
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=[audio_file, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        analysis_result = json.loads(response.text)
        print(f"[AI] Gemini 분석 완료: {analysis_result}")
        
        callback_body = {
            "user_id": user_id,
            "status": "COMPLETED",
            "analysis_data": {
                "risk_score": float(analysis_result.get("risk_score", 0.0)),
                "primary_emotion": analysis_result.get("primary_emotion", "neutral"),
                "llm_summary": analysis_result.get("llm_summary", "")
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.AI_SECRET_TOKEN}"  # 백엔드로 보낼 때 쓸 토큰
        }
        
        # ❌ (삭제) 기존의 하드코딩된 URL 조립 방식
        # callback_url = f"{BACKEND_URL}/api/v1/callbacks/jobs/{job_id}/analyzing-result"
        
        async with httpx.AsyncClient() as http_client:
            # ✅ 백엔드가 지정해준 목적지(callback_url)로 그대로 배달!
            print(f"[AI] 백엔드로 콜백 송신 중... 목적지: {callback_url}")
            res = await http_client.post(callback_url, json=callback_body, headers=headers)
            print(f"[AI] 백엔드 응답 상태코드: {res.status_code}")
            
    except Exception as e:
        print(f"[AI Critical Error] 분석 실패: {str(e)}")
        




@app.get("/")
def read_root():
    return {"message": "Welcome to AI Analysis Server (Gemini)"}

# ==========================================
# 4. 백엔드가 호출할 트리거 엔드포인트
# ==========================================
@app.post("/api/v1/analyze", status_code=status.HTTP_202_ACCEPTED)
async def trigger_analysis(
    request: AnalysisTriggerRequest, 
    background_tasks: BackgroundTasks,
    token: str = Depends(verify_api_token) 
):
    background_tasks.add_task(
        process_audio_and_callback,
        job_id=request.job_id,
        user_id=request.user_id,
        file_path=request.file_path,
        callback_url=request.callback_url  # 🌟 백그라운드 함수로 토스!
    )
    return {"message": "Analysis started in background."}