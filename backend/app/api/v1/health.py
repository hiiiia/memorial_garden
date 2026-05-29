# api/v1/health.py
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import text  # 순수 SQL 쿼리를 실행하기 위해 필요

from core.response import unified_response
from db.database import get_db

router = APIRouter()

@router.get("")
async def health_check(db: Session = Depends(get_db)):
    try:
        # DB가 살아있는지 가장 가벼운 쿼리(SELECT 1)로 핑(Ping) 테스트
        db.execute(text("SELECT 1"))
        
        # 성공 시 200 OK 일괄 적용
        return unified_response(
            status_code=status.HTTP_200_OK,
            message="Backend server and Database are running normally.",
            data={"status": "UP"}
        )
    except Exception as e:
        print(f"Health Check 실패 (DB 연결 에러): {e}")
        
        # DB 서버 다운 시 503 Service Unavailable 일괄 적용
        return unified_response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error="Backend server is running, but Database connection failed."
        )