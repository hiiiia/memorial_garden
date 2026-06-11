from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from db.database import get_db

router = APIRouter()

# AI 서버가 보내줄 데이터 스키마
class MemorySearchRequest(BaseModel):
    query_vector: list[float]
    limit: int = 3

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