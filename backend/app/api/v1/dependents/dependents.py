from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel


from db.database import get_db
from db.models import GuardianDependentMapping, Dependent

from api.v1.deps import get_current_dependent 
from core.response import unified_response

# 연동 수락/거절 요청 스키마
class LinkRespondRequest(BaseModel):
    guardian_id: str
    action: str  # "accept" (수락) 또는 "reject" (거절)

router = APIRouter()

# 어르신 연동 요청 수락/거절 API
@router.post("/respond-link")
def respond_link_request(
    request: LinkRespondRequest,
    db: Session = Depends(get_db),
    current_dependent: Dependent = Depends(get_current_dependent) # 어르신 인증 로직 적용
):
    # 1. 해당 보호자가 나에게 보낸 '대기 중(PENDING)' 상태의 요청이 있는지 조회
    mapping = db.query(GuardianDependentMapping).filter(
        GuardianDependentMapping.guardian_id == request.guardian_id,
        GuardianDependentMapping.dependent_id == current_dependent.id,
        GuardianDependentMapping.status == "PENDING"
    ).first()

    if not mapping:
        return unified_response(status_code=404, error="대기 중인 연동 요청을 찾을 수 없습니다.")

    # 2. action 값에 따라 수락 또는 거절 처리
    if request.action == "accept":
        mapping.status = "CONNECTED"
        db.commit()
        
        # TODO: 보호자에게 "어르신이 연동을 수락했습니다"라는 알림(FCM 등) 발송 로직 추가 가능
        
        return unified_response(
            status_code=200, 
            message="연동 요청을 수락했습니다. 이제 보호자와 연결됩니다."
        )
        
    elif request.action == "reject":
        mapping.status = "REJECTED"
        db.commit()
        
        # 거절 시 매핑 데이터를 완전히 삭제(delete)하고 싶다면 아래 주석을 활용하세요.
        db.delete(mapping)
        db.commit()
        
        return unified_response(
            status_code=200, 
            message="연동 요청을 거절했습니다."
        )
        
    else:
        return unified_response(status_code=400, error="잘못된 작업(action) 값입니다. 'accept' 또는 'reject'를 사용하세요.")