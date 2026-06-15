from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from db.database import get_db

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
    

@router.post("/api/v1/memory/ask_text/{dependent_id}")
async def handle_realtime_text(dependent_id: str, request: TextRequest, db: Session = Depends(get_db)):
    user_text = request.text
    
    # 1. RAG DB 검색 (기존 로직 활용)
    # query_vector = await get_embedding(user_text) # (임베딩은 로컬 함수나 API 사용)
    # similar_logs = db.query(models.Log).filter(...).limit(3).all()
    # memory_context = "\n- ".join([log.llm_summary for log in similar_logs if log.llm_summary])
    
    # 임시 테스트용 더미 컨텍스트 (실제 DB 연동 후 주석 해제)
    memory_context = "저번 주말에 손주 진우가 다녀감."
    
    # 2. AI 서버의 '실시간 전용 API' 호출 (LLM 분리 원칙 준수)
    ai_target_url = f"{settings.AI_PROXY_URL}/api/v1/fast-chat"
    
    async with httpx.AsyncClient() as client:
        try:
            ai_response = await client.post(
                ai_target_url,
                json={
                    "user_text": user_text,
                    "memory_context": memory_context
                },
                timeout=5.0 # 빠른 응답을 위해 타임아웃을 짧게 설정
            )
            ai_response.raise_for_status()
            ai_answer = ai_response.json().get("reply_text", "제가 지금은 대답하기 조금 어려워요.")
            
        except Exception as e:
            print(f"[Backend Error] AI 서버 빠른 통신 실패: {e}")
            ai_answer = "인터넷 연결이 잠시 불안정하네요. 조금 이따 다시 말씀해 주세요."

    # 3. 받아온 텍스트를 MS Edge TTS로 변환하여 스트리밍
    communicate = edge_tts.Communicate(ai_answer, "ko-KR-SunHiNeural")
    audio_stream = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_stream.write(chunk["data"])
    
    audio_stream.seek(0)
    return StreamingResponse(audio_stream, media_type="audio/mpeg")