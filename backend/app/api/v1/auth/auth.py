# api/v1/utils/
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import httpx
from datetime import timedelta
from pydantic import BaseModel
import uuid

from db.database import get_db
from db.models import Guardian
from core.config import settings
from core.response import unified_response
# JWT 출입증을 검사해서 현재 로그인한 사람이 누군지 알아내는 함수
from api.v1.deps import get_current_user

from api.v1.utils.security import encrypt_token , verify_password, get_password_hash
from api.v1.utils.jwt import create_access_token

router = APIRouter()

# Bearer 토큰 인증 객체 생성
security = HTTPBearer(auto_error=False)

class KakaoLoginRequest(BaseModel):
    code: str
    redirect_uri: str  # 프론트엔드의 콜백 주소 (예: http://localhost:3000/auth/callback)
    
class KakaoLinkRequest(BaseModel):
    code: str
    redirect_uri: str  # 예: http://localhost:3000/settings/kakao/callback

# 프론트엔드에서 넘어올 회원가입 요청 데이터
class SignupRequest(BaseModel):
    username: str
    email: str
    password: str
    name: str
    phone: str
# 카카오 회원가입 데이터 
class KakaoSignupRequest(BaseModel):
    kakao_id: str
    username: str
    email: str = None
    name: str = "Kakao-Default"
    kakao_access_token: str = None
    kakao_refresh_token: str = None
@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    일반 로그인 API (Swagger Authorize 버튼 완벽 지원)
    """
    # 1. request.username 대신 form_data.username을 사용합니다.
    guardian = db.query(Guardian).filter(Guardian.username == form_data.username).first()
    
    if not guardian or not verify_password(form_data.password, guardian.hashed_password):
        return unified_response(status_code=401, error="아이디 또는 비밀번호가 올바르지 않습니다.")
        
    service_access_token = create_access_token(
        data={"sub": str(guardian.id), "email": guardian.email}
    )
    
    # (프론트엔드를 위해 guardian 정보도 슬쩍 같이 넣어줍니다.)
    return {
        "access_token": service_access_token,
        "token_type": "bearer",
        "guardian": {
            "id": str(guardian.id),
            "username": guardian.username,
            "name": guardian.name,
            "email": guardian.email
        }
    }


@router.post("/signup")
def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """
    이메일, 비밀번호, 이름, 전화번호를 받아 새로운 보호자를 등록하는 회원가입 API입니다.
    """
    # 1. 이메일 중복 검사
    existing_user = db.query(Guardian).filter(Guardian.email == request.email).first()
    if existing_user:
        return unified_response(
            status_code=400,
            error="이미 가입된 이메일입니다."
        )
        
    
    # 2. 비밀번호를 복호화할 수 없는 안전한 해시값으로 변환
    hashed_pw = get_password_hash(request.password)
    
    

    # 3. DB 모델에 맞게 새로운 보호자 객체 생성 (카카오 토큰은 아직 없으므로 비워둠)
    new_guardian = Guardian(
        username=request.username,
        email=request.email,
        hashed_password=hashed_pw, # 평문 비밀번호가 아닌 해시값 저장
        name=request.name,
        phone=request.phone,
        
    )

    # 4. DB에 저장하고 확정(commit)
    db.add(new_guardian)
    db.commit()
    db.refresh(new_guardian) # DB에서 자동 생성된 id 등의 값을 객체에 반영

    # 5. 성공 응답 반환 (201 Created)
    return unified_response(
        status_code=201,
        message="회원가입이 성공적으로 완료되었습니다.",
        data={
            "id": str(new_guardian.id),
            "email": new_guardian.email,
            "name": new_guardian.name
        }
    )
    

@router.post("/kakao/login")
async def kakao_login(request: KakaoLoginRequest, db: Session = Depends(get_db)):
    """
    프론트엔드에서 전달받은 카카오 코드로 로그인을 처리합니다.
    (신규 유저일 경우 202 응답과 함께 가입 창으로 유도)
    리다이렉트로 접근하므로 Bearer 인증(security)을 걸면 안 됩니다.
    """
    # 1. 카카오 서버에 인가 코드를 주고 '진짜 토큰'으로 교환
    token_url = "https://kauth.kakao.com/oauth/token"
    token_data = {
        "grant_type": "authorization_code",
        "client_id": settings.KAKAO_REST_API_KEY, 
        # Client Secret이 켜져있을 경우를 대비한 안전한 처리
        "client_secret": getattr(settings, "KAKAO_CLIENT_SECRET", ""),
        "redirect_uri": request.redirect_uri, # 하드코딩 제거, 프론트가 보낸 주소 사용
        "code": request.code                  # 쿼리파라미터 대신 Body에서 꺼냄
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

    # 2. 카카오에서 발급받은 토큰으로 사용자 정보(이메일) 조회
    user_url = "https://kapi.kakao.com/v2/user/me"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    async with httpx.AsyncClient() as client:
        user_res = await client.get(user_url, headers=headers)
        user_json = user_res.json()
        
    kakao_email = user_json.get("kakao_account", {}).get("email")
    
    kakao_id = user_json.get("id")
    
    # 3. 우리 DB에서 해당 이메일을 가진 보호자 찾기
    guardian = db.query(Guardian).filter(Guardian.kakao_id == str(kakao_id)).first()
    
    # 시나리오 A: 신규 유저 (아이디 생성 페이지로 유도)
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
        
    # 시나리오 B: 기존 가입 유저 (토큰 업데이트 및 로그인 승인)
    guardian.kakao_access_token = encrypt_token(access_token)
    if refresh_token: 
        guardian.kakao_refresh_token = encrypt_token(refresh_token)
        
    db.commit()
    
    # 자체 JWT 출입증 발급 (시간 설정은 config.py 기본값 적용)
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
    current_user: Guardian = Depends(get_current_user) #  헤더의 JWT를 검사해 현재 유저를 찾아옴
):
    """
    이미 로그인한 사용자의 계정에 카카오톡 알림을 연동(토큰 저장)합니다.
    """
    # 1. 카카오 서버에 토큰 교환 요청하기
    token_url = "https://kauth.kakao.com/oauth/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"}
    
    # 주의: 카카오 디벨로퍼스에 이 redirect_uri도 등록되어 있어야 합니다!
    data = {
        "grant_type": "authorization_code",
        "client_id": settings.KAKAO_REST_API_KEY,
        "redirect_uri": request.redirect_uri, 
        "code": request.code,
    }
    
    # Client Secret을 켜두셨다면 포함
    if hasattr(settings, "KAKAO_CLIENT_SECRET") and settings.KAKAO_CLIENT_SECRET:
        data["client_secret"] = settings.KAKAO_CLIENT_SECRET

    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, headers=headers, data=data)
        
    # 2. 카카오 측 에러 처리
    if response.status_code != 200:
        print(f"[Kakao Link Error] {response.text}")
        return unified_response(
            status_code=400, 
            error="카카오 연동에 실패했습니다. 코드가 만료되었거나 잘못되었습니다."
        )

    # 3. 토큰 파싱
    token_data = response.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")

    # 4. 현재 로그인한 유저(current_user)의 정보에 암호화하여 저장
    current_user.kakao_access_token = encrypt_token(access_token)
    if refresh_token:
        current_user.kakao_refresh_token = encrypt_token(refresh_token)
        
    # 5. DB 확정
    db.commit()

    return unified_response(
        status_code=200,
        message="카카오 알림톡 연동이 성공적으로 완료되었습니다!",
        data={
            "is_kakao_linked": True
        }
    )

@router.post("/kakao/signup", status_code=status.HTTP_201_CREATED)
def kakao_signup(user_data: KakaoSignupRequest, db: Session = Depends(get_db)):
    # 1. 아이디 중복 검사
    if db.query(Guardian).filter(Guardian.username == user_data.username).first():
        
        return unified_response(
            status_code=400,
            message="이미 사용 중인 아이디입니다."
        )
    # 2. 카카오 ID 중복 검사
    if db.query(Guardian).filter(Guardian.kakao_id == user_data.kakao_id).first():
        return unified_response(
            status_code=400,
            message="이미 가입된 카카오 계정입니다."
        )

    # 3. 필수 컬럼(nullable=False) 더미 데이터 생성
    # Password > 무작위 해쉬값으로 생성
    # 카카오 이메일이 없으면 kakao_고유번호@dummy.com 형태로 생성
    # 카카오 전화번호 기본값 세팅
    
    safe_email = user_data.email if user_data.email else f"kakao_{user_data.kakao_id}@dummy.com"
    safe_password = f"kakao_dummy_{uuid.uuid4().hex}"
    safe_phone = "000-0000-0000" 

    # 4. 새 유저 객체 생성 및 저장
    new_user = Guardian(
        username=user_data.username,
        email=safe_email,
        name=user_data.name,
        kakao_id=user_data.kakao_id,
        hashed_password=safe_password,
        phone=safe_phone,
        kakao_access_token=user_data.kakao_access_token,
        kakao_refresh_token=user_data.kakao_refresh_token
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return unified_response(
            status_code=400,
            message="카카오 회원가입이 완료되었습니다.",
            data={
              "name": new_user.name  
            }
        )
#https://kauth.kakao.com/oauth/authorize?client_id=6289718b437796b5e1ed53469a6ac748&redirect_uri=http://localhost:8000/api/v1/auth/kakao/callback&response_type=code