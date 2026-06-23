from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel
from typing import Optional

# 프로젝트 구조에 맞게 임포트 경로를 수정해 주세요.
from db.database import get_db
from db.models import Dependent, GuardianDependentMapping, Guardian
from api.v1.deps import get_current_user # 현재 로그인한 보호자 정보를 가져오는 함수
from api.v1.ws.websocket_manager import device_ws_manager
from core.response import unified_response

class DependentSearchData(BaseModel):
    dependent_id: str
    username: str
    name: str
    join_date: str
    last_active: str

# 연동 요청용 데이터 스키마
class LinkRequest(BaseModel):
    dependent_id: str


router = APIRouter()

# 1. 어르신 아이디 검색 API
@router.get("/search-senior")
def search_dependent(
    username: str, 
    db: Session = Depends(get_db),
    current_user: Guardian = Depends(get_current_user) 
):
    # 1. DB에서 아이디로 피보호자(어르신) 검색
    dependent = db.query(Dependent).filter(Dependent.username == username).first()

    if not dependent:
        return unified_response(status_code=404, error="해당 아이디를 사용하는 어르신을 찾을 수 없습니다.")

    # 2. 어르신의 검색 허용 여부 체크 (is_searchable == False 이면 차단)
    if not dependent.is_searchable:
        return unified_response(status_code=403, error="검색이 허용되지 않은 계정입니다.")

    # 3. 이미 현재 보호자와 연동되어 있거나 대기 중인지 체크
    existing_mapping = db.query(GuardianDependentMapping).filter(
        GuardianDependentMapping.guardian_id == current_user.id,
        GuardianDependentMapping.dependent_id == dependent.id
    ).first()

    if existing_mapping:
        if existing_mapping.status == "PENDING":
            return unified_response(status_code=400, error="이미 수락 대기 중인 어르신입니다.")
        elif existing_mapping.status == "CONNECTED":
            return unified_response(status_code=400, error="이미 연동이 완료된 어르신입니다.")

    # 정상적인 경우 데이터 조립 및 반환
    search_data = {
        "dependent_id": dependent.id,
        "username": dependent.username,
        "name": dependent.name,
        "join_date": dependent.created_at.strftime("%Y.%m.%d") if dependent.created_at else "정보 없음",
        "last_active": "오늘 접속함" # TODO: 최근 접속 기록(Log 등) 기반으로 업데이트 필요
    }
    
    return unified_response(status_code=200, data=search_data)


# 2. 보호자 > 어르신 연동 요청 API
@router.post("/link-senior")
async def request_link_dependent(
    request: LinkRequest,
    db: Session = Depends(get_db),
    current_user: Guardian = Depends(get_current_user)
):
    # 1. 유효한 어르신인지 다시 한번 확인
    dependent = db.query(Dependent).filter(Dependent.id == request.dependent_id).first()
    if not dependent:
        return unified_response(status_code=404, error="유효하지 않은 어르신 정보입니다.")

    # 2. 중복 요청 방지
    existing_mapping = db.query(GuardianDependentMapping).filter(
        GuardianDependentMapping.guardian_id == current_user.id,
        GuardianDependentMapping.dependent_id == request.dependent_id
    ).first()

    if existing_mapping:
        return unified_response(status_code=400, error="이미 요청되었거나 연동된 상태입니다.")

    # 3. 매핑 테이블에 PENDING(대기) 상태로 데이터 추가
    new_mapping = GuardianDependentMapping(
        guardian_id=current_user.id,
        dependent_id=request.dependent_id,
        status="PENDING"
    )
    
    db.add(new_mapping)
    db.commit()

    # =================================================================
    #  웹소켓(WS)을 통해 어르신 기기로 페어링 팝업 요청 발송
    # =================================================================
    payload = {
        "action": "SHOW_PAIRING_POPUP",
        "data": {
            "mapping_id": new_mapping.id, # 어르신이 수락/거절 누를 때 보낼 매핑 식별키
            "guardian_name": current_user.name, # 팝업에 띄워줄 보호자 이름 (예: "자녀 홍길동")
            "message": f"{current_user.name} 님이 보호자 연동을 요청했습니다. 수락하시겠습니까?"
        }
    }

    # 웹소켓 전송 시도
    is_sent = await device_ws_manager.send_personal_message(
        message=payload, 
        dependent_id=str(request.dependent_id)
    )

    if is_sent:
        notification_status = "기기에 실시간 알림을 전송했습니다."
    else:
        notification_status = "기기가 오프라인 상태이므로, 기기가 켜지면 연동 대기 목록에 표시됩니다."

    return unified_response(
        status_code=201, 
        message=f"{dependent.name} 어르신에게 연동 요청을 보냈습니다. ({notification_status})"
    )
    
    
# 3. 연동 요청을 삭제
@router.delete("/cancel-link/{dependent_id}")
def cancel_link_request(
    dependent_id: str,
    db: Session = Depends(get_db),
    current_user: Guardian = Depends(get_current_user)
):
    # 1. 현재 로그인한 보호자와 해당 어르신 간의 'PENDING(대기 중)' 상태인 매핑 기록을 찾습니다.
    mapping = db.query(GuardianDependentMapping).filter(
        GuardianDependentMapping.guardian_id == current_user.id,
        GuardianDependentMapping.dependent_id == dependent_id,
        GuardianDependentMapping.status == "PENDING"
    ).first()

    if not mapping:
        return unified_response(
            status_code=404, 
            error="취소할 대기 중인 연동 요청이 존재하지 않습니다."
        )

    try:
        # 2. DB에서 해당 매핑 기록 삭제
        db.delete(mapping)
        db.commit()

        return unified_response(
            status_code=200, 
            message="연동 요청이 성공적으로 취소되었습니다."
        )
    except Exception as e:
        db.rollback()
        print(f"❌ Cancel Link Error: {str(e)}")
        return unified_response(
            status_code=500, 
            error="서버 오류로 인해 요청을 취소하지 못했습니다."
        )