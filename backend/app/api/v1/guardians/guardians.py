from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel
from typing import Optional

# 프로젝트 구조에 맞게 임포트 경로를 수정해 주세요.
from db.database import get_db
from db.models import Dependent, GuardianDependentMapping, Guardian
from api.v1.deps import get_current_user # 현재 로그인한 보호자 정보를 가져오는 함수
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


# 2. 어르신 연동 요청 API
@router.post("/link-senior")
def request_link_dependent(
    request: LinkRequest,
    db: Session = Depends(get_db),
    current_user: Guardian = Depends(get_current_user) # 실제 인증 로직 적용
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
    # TODO: 여기서 어르신의 기기(dependent.device_token)를 사용해 
    # FCM(Firebase Cloud Messaging) 등으로 푸시 알림을 발송하는 로직 추가
    # =================================================================

    return unified_response(
        status_code=201, 
        message=f"{dependent.name} 어르신에게 연동 요청을 보냈습니다."
    )