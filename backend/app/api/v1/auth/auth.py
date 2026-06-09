# api/v1/utils/

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import httpx
import uuid
from pydantic import BaseModel

from db.database import get_db
from db.models import Guardian
from core.config import settings
from core.response import unified_response
from api.v1.deps import get_current_user
from api.v1.utils.security import encrypt_token, verify_password, get_password_hash
from api.v1.utils.jwt import create_access_token

router = APIRouter()
security = HTTPBearer(auto_error=False)

# --- Pydantic 스키마 ---
class KakaoLoginRequest(BaseModel):
    code: str
    redirect_uri: str 

class KakaoLinkRequest(BaseModel):
    code: str
    redirect_uri: str 

class SignupRequest(BaseModel):
    username: str
    email: str
    password: str
    name: str
    phone: str

class KakaoSignupRequest(BaseModel):
    kakao_id: str
    username: str
    email: str = None
    name: str = "Kakao-Default"
    kakao_access_token: str = None
    kakao_refresh_token: str = None


# ----------------------------------------
# 1. 일반 로그인 / 회원가입
# ----------------------------------------
@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """일반 로그인 API"""
    guardian = db.query(Guardian).filter(Guardian.username == form_data.username).first()
    
    if not guardian or not verify_password(form_data.password, guardian.hashed_password):
        return unified_response(status_code=401, error="아이디 또는 비밀번호가 올바르지 않습니다.")
        
    service_access_token = create_access_token(
        data={"sub": str(guardian.id), "email": guardian.email}
    )
    
    # unified_response로 규격 통일
    return unified_response(
        status_code=200,
        message="로그인 성공",
        data={
            "access_token": service_access_token,
            "token_type": "bearer",
            "guardian": {
                "id": str(guardian.id),
                "username": guardian.username,
                "name": guardian.name,
                "email": guardian.email
            }
        }
    )

@router.post("/signup")
def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """일반 회원가입 API"""
    existing_user = db.query(Guardian).filter(Guardian.email == request.email).first()
    if existing_user:
        return unified_response(status_code=400, error="이미 가입된 이메일입니다.")
        
    hashed_pw = get_password_hash(request.password)
    
    new_guardian = Guardian(
        username=request.username,
        email=request.email,
        hashed_password=hashed_pw,
        name=request.name,
        phone=request.phone,
    )

    db.add(new_guardian)
    db.commit()
    db.refresh(new_guardian) 

    return unified_response(
        status_code=201,
        message="회원가입이 성공적으로 완료되었습니다.",
        data={
            "id": str(new_guardian.id),
            "email": new_guardian.email,
            "name": new_guardian.name
        }
    )
    

# ----------------------------------------
# 2. 카카오 소셜 로그인 / 회원가입 / 알림 연동
# ----------------------------------------
@router.post("/kakao/login")
async def kakao_login(request: KakaoLoginRequest, db: Session = Depends(get_db)):
    """카카오 로그인 처리 (신규 유저일 경우 202 응답으로 회원가입 유도)"""
    token_url = "https://kauth.kakao.com/oauth/token"
    token_data = {
        "grant_type": "authorization_code",
        "client_id": settings.KAKAO_REST_API_KEY, 
        "client_secret": getattr(settings, "KAKAO_CLIENT_SECRET", ""),
        "redirect_uri": request.redirect_uri, 
        "code": request.code 
    }
    
    async with httpx.AsyncClient() as client:
        token_res = await client.post(token_url, data=token_data)
        token_json = token_res.json()
        
        if "error" in token_json:
            return unified_response(
                status_code=400,
                error=f"카카오 토큰 발급 실패: {token_json.get('error_description', token_json)}"
            )
            
        access_token = token_json.get("access_token")
        refresh_token = token_json.get("refresh_token")

    user_url = "https://kapi.kakao.com/v2/user/me"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    async with httpx.AsyncClient() as client:
        user_res = await client.get(user_url, headers=headers)
        user_json = user_res.json()
        
    kakao_email = user_json.get("kakao_account", {}).get("email")
    kakao_id = user_json.get("id")
    
    guardian = db.query(Guardian).filter(Guardian.kakao_id == str(kakao_id)).first()
    
    if not guardian:
        return unified_response(
            status_code=202, 
            message="신규 사용자입니다. 아이디 생성(회원가입) 페이지로 이동합니다.",
            data={
                "is_new_user": True,
                "kakao_email": kakao_email,
                "kakao_id": str(kakao_id),
                "temp_kakao_access_token": encrypt_token(access_token), 
                "temp_kakao_refresh_token": encrypt_token(refresh_token) if refresh_token else None
            }
        )
        
    guardian.kakao_access_token = encrypt_token(access_token)
    if refresh_token: 
        guardian.kakao_refresh_token = encrypt_token(refresh_token)
        
    db.commit()
    
    service_access_token = create_access_token(
        data={"sub": str(guardian.id), "email": guardian.email} 
    )
    
    return unified_response(
        status_code=200,
        message="카카오 연동 및 로그인 성공",
        data={
            "access_token": service_access_token,
            "token_type": "bearer",
            "guardian": {
                "id": str(guardian.id),
                "name": guardian.name,
                "email": guardian.email
            }
        }
    )

@router.post("/kakao/link")
async def link_kakao(
    request: KakaoLinkRequest,
    db: Session = Depends(get_db),
    current_user: Guardian = Depends(get_current_user) 
):
    """기존 로그인 사용자의 카카오 알림톡 연동"""
    token_url = "https://kauth.kakao.com/oauth/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"}
    
    data = {
        "grant_type": "authorization_code",
        "client_id": settings.KAKAO_REST_API_KEY,
        "redirect_uri": request.redirect_uri, 
        "code": request.code,
    }
    
    if hasattr(settings, "KAKAO_CLIENT_SECRET") and settings.KAKAO_CLIENT_SECRET:
        data["client_secret"] = settings.KAKAO_CLIENT_SECRET

    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, headers=headers, data=data)
        
    if response.status_code != 200:
        print(f"[Kakao Link Error] {response.text}")
        return unified_response(
            status_code=400, 
            error="카카오 연동에 실패했습니다. 코드가 만료되었거나 잘못되었습니다."
        )

    token_data = response.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")

    current_user.kakao_access_token = encrypt_token(access_token)
    if refresh_token:
        current_user.kakao_refresh_token = encrypt_token(refresh_token)
        
    db.commit()

    return unified_response(
        status_code=200,
        message="카카오 알림톡 연동이 성공적으로 완료되었습니다!",
        data={"is_kakao_linked": True}
    )

@router.post("/kakao/signup", status_code=status.HTTP_201_CREATED)
def kakao_signup(user_data: KakaoSignupRequest, db: Session = Depends(get_db)):
    """카카오 신규 유저 회원가입 최종 승인"""
    if db.query(Guardian).filter(Guardian.username == user_data.username).first():
        return unified_response(status_code=400, error="이미 사용 중인 아이디입니다.")
        
    if db.query(Guardian).filter(Guardian.kakao_id == user_data.kakao_id).first():
        return unified_response(status_code=400, error="이미 가입된 카카오 계정입니다.")

    safe_email = user_data.email if user_data.email else f"kakao_{user_data.kakao_id}@dummy.com"
    # 더미 비밀번호에도 해시 함수를 거쳐 보안 스캐너 경고 방지
    raw_dummy_password = f"kakao_dummy_{uuid.uuid4().hex}"
    safe_hashed_password = get_password_hash(raw_dummy_password)
    safe_phone = "000-0000-0000" 

    new_user = Guardian(
        username=user_data.username,
        email=safe_email,
        name=user_data.name,
        kakao_id=user_data.kakao_id,
        hashed_password=safe_hashed_password,
        phone=safe_phone,
        kakao_access_token=user_data.kakao_access_token,
        kakao_refresh_token=user_data.kakao_refresh_token
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # 버그 수정: status_code 400 -> 201
    return unified_response(
        status_code=201, 
        message="카카오 회원가입이 완료되었습니다.",
        data={"name": new_user.name}
    )

#https://kauth.kakao.com/oauth/authorize?client_id=6289718b437796b5e1ed53469a6ac748&redirect_uri=http://localhost:8000/api/v1/auth/kakao/callback&response_type=code