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


# --- 어르신(장치)용 API Key 인증 체계 ---
# auto_error=False로 설정해야 헤더가 없을 때 자체 커스텀 401 에러를 띄울 수 있습니다.
security_bearer = HTTPBearer(auto_error=False)

def get_current_dependent(
    credentials: HTTPAuthorizationCredentials = Depends(security_bearer),
    x_dependent_id: str = Header(..., description="라즈베리파이에 할당된 어르신 고유 ID"), # 장치가 자신이 누구인지 알려주는 헤더
    db: Session = Depends(get_db)
):
    """
    공통 API_SECRET_TOKEN을 검증하고, 헤더의 ID를 통해 어르신(Dependent) 객체를 반환합니다.
    """
    # 1. 장치 공통 시크릿 키 검증
    if credentials.credentials != settings.API_SECRET_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized. Invalid or missing token."
        )
        
    # 2. X-Dependent-Id 헤더를 통해 특정 어르신 식별
    dependent = db.query(Dependent).filter(Dependent.id == x_dependent_id).first()
    if dependent is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="어르신 정보를 찾을 수 없습니다. 헤더의 ID를 확인하세요."
        )
        
    return dependent