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
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    job_id = f"fast_{uuid.uuid4().hex[:8]}"
    callback_url = f"http://backend:8000/api/v1/callbacks/jobs/{job_id}/fast-chat" # (경로 주의: /memory 포함 여부 확인)
    ai_target_url = f"{settings.AI_PROXY_URL}/api/v1/fast-chat" 

    # 1. ⚡ [FastChat 테이블] PROCESSING 상태로 생성
    try:
        new_chat = models.FastChat(
            id=job_id,
            dependent_id=dependent_id,
            user_text=request.text,
            status="PROCESSING"
        )
        db.add(new_chat)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[Backend Error] FastChat DB 생성 실패: {e}")
        raise HTTPException(status_code=500, detail="Database Error")

    # 2. 🧠 [Log 테이블 조회] 진짜 과거 기억 가져오기
    recent_logs = db.query(models.Log).filter(
        models.Log.dependent_id == dependent_id,
        models.Log.llm_summary.is_not(None)
    ).order_by(models.Log.created_at.desc()).limit(3).all()
    
    memory_context = "\n- ".join([log.llm_summary for log in recent_logs if log.llm_summary])
    if not memory_context:
        memory_context = "과거 기억이나 이전 대화가 아직 없습니다."

    # 💡 [추가] AI 서버로 보낼 보안 토큰 헤더 생성
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.AI_SECRET_TOKEN}"
    }
    
    # 3. 🌐 AI 서버로 백그라운드 전송
    async def forward_to_ai():
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    ai_target_url, 
                    json={
                        "job_id": job_id,
                        "user_text": request.text,
                        "memory_context": memory_context,
                        "callback_url": callback_url
                    }, 
                    headers=headers,
                    timeout=5.0
                )
                # 💡 HTTP 4xx, 5xx 에러가 발생하면 무시하지 않고 except 블록으로 던집니다.
                response.raise_for_status() 
                
            except Exception as e:
                print(f"[Backend Error] AI 서버 전달 실패 (타임아웃 또는 연결 거부): {e}")
                
                # 💡 [추가된 로직] AI 서버 호출 실패 시 DB 상태를 FAILED로 즉시 변경
                # 백그라운드 태스크이므로 메인 세션(db) 대신 독립적인 세션을 생성합니다.
                bg_db = next(get_db()) # 프로젝트의 DB 세션 생성 방식에 맞게 수정 (예: SessionLocal())
                try:
                    failed_chat = bg_db.query(models.FastChat).filter(models.FastChat.id == job_id).first()
                    if failed_chat:
                        failed_chat.status = "FAILED"
                        bg_db.commit()
                        print(f"[Backend Recovery] Job ID ({job_id})의 상태를 FAILED로 변경하여 에이전트 폴링을 종료시킵니다.")
                except Exception as db_err:
                    bg_db.rollback()
                    print(f"[Backend Error] FAILED 상태 업데이트 중 DB 에러: {db_err}")
                finally:
                    bg_db.close() # 세션 반환

    background_tasks.add_task(forward_to_ai)
    return {"status": "processing", "job_id": job_id}


# DB를 조회해서 작업이 끝났으면 오디오 파일 URL을 던져줌
@router.get("/check_status/{job_id}")
async def check_tts_status(job_id: str, db: Session = Depends(get_db)):
    #  FastChat 테이블 조회!
    chat_record = db.query(models.FastChat).filter(models.FastChat.id == job_id).first()
    
    if not chat_record:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if chat_record.status == "COMPLETED" and chat_record.reply_audio_url:
        return {
            "status": "COMPLETED", 
            "reply_text": chat_record.reply_text,
            "audio_url": chat_record.reply_audio_url
        }
    elif chat_record.status == "FAILED":
        return {"status": "FAILED"}
        
    return {"status": "PROCESSING"}