from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from db.database import get_db
from db.models import GuardianDependentMapping, Dependent, Log
from db import models

from api.v1.deps import get_current_dependent_jwt 
from api.v1.utils.security import get_password_hash
from api.v1.utils.jwt import create_access_token
from api.v1.deps import validate_hw_key
from core.response import unified_response
from api.v1.utils.notifier import send_emergency_alert, send_kakao_alert
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

class EmergencyRequest(BaseModel):
    mac_address: str
    
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
    
@router.post("/emergency")
def alert_emergency(
    request: EmergencyRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    하드웨어 전용 긴급 호출 API (인증 X)
    MAC 주소를 받아 연결된 보호자들에게 즉시 긴급 알림을 발송합니다.
    """
    mac_address = request.mac_address
    print(f"[Emergency] 🚨 기기(MAC: {mac_address})에서 긴급 호출 발생!")

    # 2. MAC 주소(dependent_id)와 연결된(CONNECTED) 보호자 매핑 목록 조회
    connected_mappings = db.query(models.GuardianDependentMapping).filter(
        models.GuardianDependentMapping.dependent_id == mac_address,
        models.GuardianDependentMapping.status == "CONNECTED"
    ).all()

    if not connected_mappings:
        print(f"[Emergency Warning] 매핑된 보호자가 없습니다. (MAC: {mac_address})")
        # 보호자가 없더라도 HW 기기에는 에러를 뱉지 않고 200 OK를 주어 시스템이 멈추지 않게 합니다.
        return {"status": "success", "message": "No connected guardians found."}

    # 3. 어르신 이름 가져오기 (알림 발송용)
    # 매핑 데이터 중 첫 번째 레코드에서 dependent 객체를 꺼냅니다.
    first_mapping = connected_mappings[0]
    target_name = first_mapping.dependent.name if hasattr(first_mapping, 'dependent') and first_mapping.dependent else "어르신"

    # 4. 각 보호자에게 백그라운드로 긴급 알림 발송
    for mapping in connected_mappings:
        guardian_obj = mapping.guardian
        if not guardian_obj:
            continue

        print(f"[Alert 발송] {guardian_obj.name} 보호자에게 긴급 알림을 예약합니다.")

        # 하드웨어 호출이므로 위험도는 무조건 최고치(100)로 설정하고, 기본 메시지를 세팅합니다.
        risk_score = 100.0
        summary = "기기에서 긴급 호출(SOS)이 발생했습니다!"
        emergency_text = "어르신 기기의 긴급 버튼이 눌렸습니다. 즉시 확인해 주세요."

        background_tasks.add_task(
            send_emergency_alert,
            risk_score=risk_score,
            summary=summary,
            text=emergency_text, 
            dependent_name=target_name,
            guardian_phone=guardian_obj.phone,
            guardian_name=guardian_obj.name
        )
        background_tasks.add_task(
            send_kakao_alert,
            guardian=guardian_obj,
            dependent_name=target_name,
            risk_score=risk_score,
            summary=summary,
            db=db
        )

    return {"status": "success", "message": "Emergency alerts dispatched successfully."}
    

@router.post("/device/register")
def register_device(request: DeviceRegisterRequest, db: Session = Depends(get_db), _ = Depends(validate_hw_key)):
    """엣지 디바이스 부팅 시 DEVICE_HW_KEY 검증
    자동 등록 및 JWT 토큰(인증) 동시 발급"""
    
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
    
    
@router.get("/diary")
def get_picture_diaries(
    limit: int = 10,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_dep: Dependent = Depends(get_current_dependent_jwt) # 토큰을 통해 어르신 객체 자동 로드!
):
    """
    어르신 기기(React 프론트엔드)에서 본인의 그림일기 목록을 조회하는 API
    """
    # 1. 해당 어르신의 일기 데이터만 최신순으로 가져오기
    # (주의: Memory.dependent_id 와 current_dep.id 가 매칭되는지 확인)
    diaries = db.query(Log).filter(
        Log.dependent_id == current_dep.id,
    ).order_by(Log.created_at.desc()).offset(offset).limit(limit).all()
    
    # 2. React 화면에서 렌더링하기 편하도록 예쁘게 가공
    result = []
    for diary in diaries:
        result.append({
            "id": diary.id,
            "content": diary.diary_text,       # 일기 본문 (텍스트)
            "image_url": diary.image_url,   # AI가 생성한 이미지 주소 (S3 URL 등)
            # 날짜를 어르신이 보기 편한 문자열 형태로 변환
            "created_at": diary.created_at.strftime("%Y년 %m월 %d일") 
        })
        
    # 3. 통일된 응답 포맷으로 반환
    return unified_response(
        status_code=200,
        message="그림일기 조회에 성공했습니다.",
        data={
            "total_fetched": len(result),
            "diaries": result
        }
    )