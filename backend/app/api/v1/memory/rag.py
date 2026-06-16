from fastapi import APIRouter, Depends, BackgroundTasks, status, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from db.database import get_db
from db import models
from core.config import settings
import httpx
import uuid

router = APIRouter()

# AI 서버가 보내줄 데이터 스키마
class MemorySearchRequest(BaseModel):
    query_vector: list[float]
    limit: int = 3

# 라즈베리의 기억 검색 요청 스키마
class TextRequest(BaseModel):
    text: str


# 벡터 검색이므로 Get 대신 Post로 하는게 표준
@router.post("/search/{dependent_id}")
async def search_senior_memory(
    dependent_id: str, 
    payload: MemorySearchRequest,
    db: Session = Depends(get_db)
):
    try:
        from db.models import Log
        
        # 백엔드는 유사도 검색만
        similar_logs = db.query(Log).filter(
            Log.dependent_id == dependent_id,
            Log.vector_embedding.is_not(None) # 벡터가 없는 로그는 제외
        ).order_by(
            Log.vector_embedding.cosine_distance(payload.query_vector)
        ).limit(payload.limit).all()

        # 검색된 과거의 요약본들을 리스트로 추출
        memories = [log.llm_summary for log in similar_logs if log.llm_summary]
        
        return {"status": "success", "memories": memories}

    except Exception as e:
        print(f"[RAG Retrieval Error] DB 검색 실패: {e}")
        return {"status": "error", "memories": []}

    
# text로 rag 검색
# --- 라즈베리 파이로부터 텍스트 수신 및 AI 위임 ---
@router.post("/ask_text/{dependent_id}", status_code=status.HTTP_202_ACCEPTED)
async def handle_realtime_text_trigger(
    dependent_id: str, 
    request: TextRequest, 
    background_tasks: BackgroundTasks
):
    job_id = f"fast_{uuid.uuid4().hex[:8]}"
    callback_url = f"http://backend:8000/api/v1/callbacks/jobs/{job_id}/fast-chat"
    memory_context = "저번 주말에 손주 진우가 다녀감." # 임시 더미 데이터
    
    ai_target_url = f"{settings.AI_PROXY_URL}/api/v1/fast-chat"

    # AI 서버로 콜백 주소와 함께 비동기 요청 (라즈베리 파이 응답을 막지 않음)
    async def forward_to_ai():
        async with httpx.AsyncClient() as client:
            try:
                await client.post(ai_target_url, json={
                    "job_id": job_id,
                    "user_text": request.text,
                    "memory_context": memory_context,
                    "callback_url": callback_url
                }, timeout=5.0)
            except Exception as e:
                print(f"[Backend Error] AI 서버 전달 실패: {e}")

    background_tasks.add_task(forward_to_ai)

    # 라즈베리 파이에게는 접수증(job_id)만 즉시 리턴
    return {"status": "processing", "job_id": job_id}

# DB를 조회해서 작업이 끝났으면 오디오 파일 URL을 던져줌
@router.get("/check_status/{job_id}")
async def check_tts_status(job_id: str, db: Session = Depends(get_db)):
    log_record = db.query(models.Log).filter(models.Log.id == job_id).first()
    
    if not log_record:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if log_record.status == "COMPLETED" and log_record.reply_audio_url:
        return {
            "status": "COMPLETED", 
            "reply_text": log_record.reply_text,
            "audio_url": log_record.reply_audio_url
        }
    elif log_record.status == "FAILED":
        return {"status": "FAILED"}
        
    # 아직 처리 중 (PROCESSING)
    return {"status": "PROCESSING"}