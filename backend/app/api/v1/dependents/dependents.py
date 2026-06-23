from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from pydantic import BaseModel

from db.database import get_db
from db.models import GuardianDependentMapping, Dependent

#from api.v1.deps import get_current_dependent 
from api.v1.utils.security import get_password_hash
from api.v1.utils.jwt import create_access_token
from core.response import unified_response
import uuid

# 연동 수락/거절 요청 스키마
class LinkRespondRequest(BaseModel):
    guardian_id: str
    action: str  # "accept" (수락) 또는 "reject" (거절)

class DeviceRegisterRequest(BaseModel):
    hw_id: str
    username: str
    name: str
    age: int
    
router = APIRouter()

# @router.post("/respond-link")
# def respond_link_request(
#     request: LinkRespondRequest,
#     db: Session = Depends(get_db),
#     current_dependent: Dependent = Depends(get_current_dependent) # 어르신 인증 로직 적용
# ):
#     # 1. 해당 보호자가 나에게 보낸 '대기 중(PENDING)' 상태의 요청이 있는지 조회
#     mapping = db.query(GuardianDependentMapping).filter(
#         GuardianDependentMapping.guardian_id == request.guardian_id,
#         GuardianDependentMapping.dependent_id == current_dependent.id,
#         GuardianDependentMapping.status == "PENDING"
#     ).first()

#     if not mapping:
#         return unified_response(status_code=404, error="대기 중인 연동 요청을 찾을 수 없습니다.")

#     # 2. action 값에 따라 수락 또는 거절 처리
#     if request.action == "accept":
#         mapping.status = "CONNECTED"
#         db.commit()
        
#         # TODO: 보호자에게 "어르신이 연동을 수락했습니다"라는 알림(FCM 등) 발송 로직 추가 가능
        
#         return unified_response(
#             status_code=200, 
#             message="연동 요청을 수락했습니다. 이제 보호자와 연결됩니다."
#         )
        
#     elif request.action == "reject":
#         mapping.status = "REJECTED"
#         db.commit()
        
#         # 거절 시 매핑 데이터를 완전히 삭제(delete)하고 싶다면 아래 주석을 활용하세요.
#         db.delete(mapping)
#         db.commit()
        
#         return unified_response(
#             status_code=200, 
#             message="연동 요청을 거절했습니다."
#         )
        
#     else:
#         return unified_response(status_code=400, error="잘못된 작업(action) 값입니다. 'accept' 또는 'reject'를 사용하세요.")
    
    
@router.post("/device/register")
def register_device(request: DeviceRegisterRequest, db: Session = Depends(get_db)):
    """엣지 디바이스 부팅 시 자동 등록 및 JWT 토큰(인증) 동시 발급"""
    
    # 1. MAC 주소를 기반으로 기기 전용 JWT 토큰 생성
    # payload의 'sub'에 MAC 주소를 넣고, 역할(role)을 device로 명시
    new_jwt_token = create_access_token(data={"sub": request.hw_id, "role": "device"})
    
    existing_device = db.query(Dependent).filter(Dependent.id == request.hw_id).first()
    
    # 2. 이미 등록된 기기인 경우 (기존 유저 로그인과 동일한 효과)
    if existing_device:
        existing_device.device_token = new_jwt_token # DB 토큰 갱신
        existing_device.username = request.username
        existing_device.name = request.name
        existing_device.age = request.age
        db.commit()
        return unified_response(
            status_code=200, 
            message="기존 기기 인증 성공 및 토큰 갱신", 
            data={
                "access_token": new_jwt_token, 
                "dependent_id": str(existing_device.id)
            }
        )

    # 3. 처음 켜진 신규 기기인 경우 (자동 회원가입)
    random_password = uuid.uuid4().hex
    hashed_pw = get_password_hash(random_password)
    
    new_dependent = Dependent(
        id=request.hw_id,                                
        username=request.username,                       
        hashed_password=hashed_pw,                       
        is_searchable=True,                              
        name=request.name,                               
        age=request.age,                                 
        device_token=new_jwt_token  # 새로 발급한 JWT 저장                   
    )
    
    db.add(new_dependent)
    db.commit()
    
    return unified_response(
        status_code=201, 
        message="신규 기기 자동 등록 및 인증 완료", 
        data={
            "access_token": new_jwt_token, 
            "dependent_id": request.hw_id
        }
    )