# app/api/v1/deps.py
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt

from core.config import settings
from db.database import get_db
from db.models import Guardian
from core.response import unified_response

# 프론트엔드가 헤더에 'Bearer <토큰>' 형태로 보내면 여기서 낚아챕니다.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    JWT 토큰을 검증하고, 현재 로그인한 보호자(Guardian) 객체를 반환합니다.
    """
    try:
        # 1. 토큰 열어보기 (위조되었거나 만료되면 여기서 에러 발생)
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM])
        guardian_id: str = payload.get("sub")
        
        if guardian_id is None:
                return unified_response(status_code=401, error="이메일 또는 비밀번호가 올바르지 않습니다." )
        
            
    except jwt.PyJWTError: # 토큰 만료 또는 조작됨
        return unified_response(status_code=401, error="유효하지 않거나 만료된 토큰입니다." )
        
    # 2. DB에서 해당 ID의 사용자 찾기
    user = db.query(Guardian).filter(Guardian.id == guardian_id).first()
    if user is None:
        return unified_response(status_code=401, error="사용자를 찾을 수 없습니다.")
        
    return user