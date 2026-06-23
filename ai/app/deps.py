from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings

# HTTPBearer를 사용하여 헤더에서 토큰을 추출 (auto_error=False로 커스텀 에러 처리)
security_bearer = HTTPBearer(auto_error=False)

def validate_ai_secret_token(
    credentials: HTTPAuthorizationCredentials = Depends(security_bearer)
):
    """
    AI 오케스트레이터 서버 전용 시크릿 토큰을 검증합니다.
    헤더 형식: Authorization: Bearer <AI_SECRET_TOKEN>
    """
    if not credentials or credentials.credentials != settings.AI_SECRET_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid or missing AI Secret Token"
        )
    return True