from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import jwt

from core.config import settings
from db.database import get_db
from db.models import Guardian, Dependent

# --- 보호자(앱)용 JWT 인증 체계 ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    JWT 토큰을 검증하고, 현재 로그인한 보호자(Guardian) 객체를 반환합니다.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM])
        guardian_id: str = payload.get("sub")
        
        if guardian_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="토큰 정보가 올바르지 않습니다.")
            
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="만료된 토큰입니다.")
    except jwt.PyJWTError: 
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 토큰입니다.")
        
    user = db.query(Guardian).filter(Guardian.id == guardian_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="보호자 정보를 찾을 수 없습니다.")
        
    return user


security_bearer = HTTPBearer(auto_error=False)

# --- 어르신 기기 jwt 인증 ---
def verify_hw_jwt_token(token: str) -> str:
    """
    JWT를 검증하고, 성공 시 dependent_id(sub)를 반환합니다.
    실패 시 Exception을 발생시킵니다.
    """
    try:
        # 1. JWT 디코딩 및 검증
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        
        # 2. 'sub' 확인
        dependent_id = payload.get("sub")
        if not dependent_id:
            raise ValueError("Token payload missing sub")
            
        return dependent_id

    except jwt.ExpiredSignatureError:
        raise ValueError("Token expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")