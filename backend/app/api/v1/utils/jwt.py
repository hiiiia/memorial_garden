import jwt
from datetime import datetime, timedelta
from typing import Optional
from core.config import settings

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    사용자 정보(data)를 담은 JWT 토큰을 생성합니다.
    """
    to_encode = data.copy()
    
    # 1. 만료 시간이 인자로 넘어오면 그걸 쓰고, 없으면 config.py의 기본값(30일)을 사용
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
    to_encode.update({"exp": expire})
    
    # 2. config.py에 정의한 비밀키와 알고리즘으로 서명하여 토큰 발행
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.JWT_SECRET_KEY, 
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt