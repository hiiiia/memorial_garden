# app/api/routes/dashboard.py

from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.orm import Session
from datetime import datetime

from api.v1.deps import get_current_user

from db.database import get_db
from db.models import Guardian
from core.response import unified_response

router = APIRouter()

@router.get("/{guardian_id}/dashboard")
def get_guardian_dashboard(
    guardian_id: str = Path(..., description="보호자 고유 ID"),
    user_id: str = Query(..., description="어르신 고유 ID"),
    date: datetime = Query(..., description="조회 기준 일시"),
    current_user: Guardian = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. 권한 체크 (토큰의 ID와 URL의 ID가 같은지)
    if str(current_user.id) != guardian_id:
        return unified_response(status_code=403, error="Permission denied.")

    # 2. 대시보드 UI에 완벽하게 맞춘 응답 데이터 조립
    # (실제 서비스 시에는 DB에서 조회한 데이터로 교체될 영역입니다)
    dashboard_data = {
        "guardian_name": current_user.name if current_user.name else "가족",
        "senior": {
            "name": "김영희",
            "status": "연동 중"
        },
        
        # [위젯 1] 오늘의 상태
        "today_condition": {
            "state": "STABLE", # STABLE(안정), WARNING(주의), DANGER(위험)
            "label": "안정",
            "description": "특이사항이 없습니다.",
            "color_code": "#7A8B5F" # 프론트엔드 렌더링 편의를 위한 색상값
        },

        # [위젯 2] 위험도
        "risk_assessment": {
            "score": 32,
            "level": "낮음",
            "status_text": "안정적인 상태입니다."
        },

        # [위젯 3] 마지막 대화
        "last_interaction": {
            "time_label": "오늘 오전 9:12",
            "duration_label": "AI와 15분 대화"
        },

        # [위젯 4] 최근 알림
        "recent_alerts": [
            {
                "id": 1,
                "content": "오늘 일기가 공유되었습니다.",
                "time_ago": "오전 9:15",
                "type": "INFO"
            },
            {
                "id": 2,
                "content": "위험도 변동이 없습니다.",
                "time_ago": "어제",
                "type": "STABLE"
            },
            {
                "id": 3,
                "content": "도움 요청이 없었습니다.",
                "time_ago": "어제",
                "type": "SAFE"
            }
        ]
    }

    return unified_response(
        status_code=202,
        message="Dashboard data fetched successfully.",
        data=dashboard_data
    )