# api/v1/utils/
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import httpx
from datetime import timedelta

from db.database import get_db
from db.models import Guardian
from core.config import settings
from core.response import unified_response
from api.v1.utils.crypto import encrypt_token 
from api.v1.utils.jwt import create_access_token


router = APIRouter()

# Bearer 토큰 인증 객체 생성
security = HTTPBearer(auto_error=False)


@router.get("/kakao/callback")
async def kakao_callback(code: str, db: Session = Depends(get_db)):
    """
    카카오 로그인 성공 후 '인가 코드(code)'를 받아오는 콜백 엔드포인트입니다.
    외부 브라우저 리다이렉트로 접근하므로 Bearer 인증(security)을 걸면 안 됩니다.
    """
    # 1. 카카오 서버에 인가 코드를 주고 '진짜 토큰'으로 교환
    token_url = "https://kauth.kakao.com/oauth/token"
    token_data = {
        "grant_type": "authorization_code",
        "client_id": settings.KAKAO_REST_API_KEY, 
        "client_secret": settings.KAKAO_CLIENT_SECRET,
        "redirect_uri": "http://localhost:8000/api/v1/auth/kakao/callback",
        "code": code 
    }
    
    async with httpx.AsyncClient() as client:
        token_res = await client.post(token_url, data=token_data)
        token_json = token_res.json()
        
        if "error" in token_json:
            # unified_response로 에러 반환
            return unified_response(
                status_code=400,
                error=f"카카오 토큰 발급 실패: {token_json.get('error_description', token_json)}"
            )
            
        access_token = token_json.get("access_token")
        refresh_token = token_json.get("refresh_token")

    # 2. 카카오에서 발급받은 토큰으로 사용자 정보(이메일) 조회
    user_url = "https://kapi.kakao.com/v2/user/me"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    async with httpx.AsyncClient() as client:
        user_res = await client.get(user_url, headers=headers)
        user_json = user_res.json()
        
    kakao_email = user_json.get("kakao_account", {}).get("email")
    
    # 3. 우리 DB에서 해당 이메일을 가진 보호자 찾기
    guardian = db.query(Guardian).filter(Guardian.email == kakao_email).first()
    
    # 임시 매칭 로직
    if not guardian:
        guardian = db.query(Guardian).first()
        if not guardian:
            # 🌟 수정됨: HTTPException 대신 unified_response로 에러 반환
            return unified_response(
                status_code=404,
                error="DB에 보호자 정보가 없습니다."
            )
            
    # 4. 토큰을 암호화하여 DB에 저장
    guardian.kakao_access_token = encrypt_token(access_token)
    if refresh_token: 
        guardian.kakao_refresh_token = encrypt_token(refresh_token)
        
    db.commit()
    
    
    access_token_expires = timedelta(hours=24) # 24시간 유효
    service_access_token = create_access_token(
        # 토큰 안에 누구의 토큰인지 알 수 있도록 보호자의 ID와 이메일을 담습니다.
        data={"sub": str(guardian.id), "email": guardian.email}, 
        expires_delta=access_token_expires
    )
    
    
    return unified_response(
        status_code=200,
        message="카카오 연동 및 로그인 성공",
        data={
            "access_token": service_access_token, # 프론트엔드가 이 값을 LocalStorage에 저장하게 됨
            "token_type": "bearer",
            "guardian": {
                "id": str(guardian.id),
                "name": guardian.name,
                "email": guardian.email
            }
        }
    )


#https://kauth.kakao.com/oauth/authorize?client_id=6289718b437796b5e1ed53469a6ac748&redirect_uri=http://localhost:8000/api/v1/auth/kakao/callback&response_type=code