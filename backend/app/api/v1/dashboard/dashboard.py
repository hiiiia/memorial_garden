from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, date as dt_date
from typing import Optional
from datetime import timedelta
import calendar

from api.v1.deps import get_current_user
from db.database import get_db
from db.models import Guardian, Dependent, GuardianDependentMapping, Log, Alert
from core.response import unified_response

router = APIRouter()

@router.get("/{guardian_id}/dashboard")
def get_guardian_dashboard(
    guardian_id: str = Path(..., description="보호자 고유 ID"),
    user_id: str = Query(..., description="어르신 고유 ID"),
    date: Optional[str] = Query(None, description="조회 기준 날짜 (ISO String 또는 YYYY-MM-DD)"),
    current_user: Guardian = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. 권한 체크
    if str(current_user.id) != guardian_id:
        return unified_response(status_code=403, error="Permission denied.")

    # 2. 보호자-어르신 연동 관계 및 상태 확인
    mapping = db.query(GuardianDependentMapping).filter(
        GuardianDependentMapping.guardian_id == guardian_id,
        GuardianDependentMapping.dependent_id == user_id
    ).first()

    if not mapping:
        return unified_response(status_code=404, error="연동 정보가 존재하지 않습니다. 어르신을 먼저 등록해주세요.")

    # 어르신 측 수락 대기 상태(PENDING) 예외 처리
    if mapping.status == "PENDING":
        dependent = db.query(Dependent).filter(Dependent.id == user_id).first()
        return unified_response(
            status_code=202,
            message="어르신의 연동 수락을 대기 중입니다.",
            data={
                "status": "PENDING", 
                "senior_name": dependent.name if dependent else "어르신"
            }
        )

    if mapping.status == "REJECTED":
        return unified_response(status_code=400, error="어르신에 의해 연동 요청이 거절되었습니다.")

    # 3. 어르신 정보 조회
    dependent = db.query(Dependent).filter(Dependent.id == user_id).first()
    if not dependent:
        return unified_response(status_code=404, error="어르신 정보를 찾을 수 없습니다.")

    # 4. 날짜 파싱 및 해당 날짜의 최신 로그(Log) 조회
    if date:
        try:
            target_date = datetime.fromisoformat(date.replace("Z", "")).date()
        except ValueError:
            target_date = datetime.strptime(date[:10], "%Y-%m-%d").date()
    else:
        target_date = dt_date.today()

    latest_log = db.query(Log).filter(
        Log.dependent_id == user_id,
        func.date(Log.created_at) == target_date
    ).order_by(Log.created_at.desc()).first()

    # 5. 프론트엔드 포맷 초기화 (기본값 설정)
    state = "good"
    label = "안정"
    description = "오늘 진행된 대화가 없거나 특이사항이 없습니다."
    color_code = "#388E3C"
    risk_score = 0
    level = "낮음"
    status_text = "안정적인 상태입니다."
    time_label = "대화 기록 없음"
    duration_label = "라즈베리파이 연결 상태를 확인하세요."

    if latest_log:
        risk_score = int(latest_log.risk_score)
        
        if risk_score >= 70:
            state = "bad"
            label = "위험"
            color_code = "#D32F2F"
            level = "위험"
            status_text = "인지 저하 혹은 높은 우울 징후가 포착되었습니다. 주의 깊게 살펴주세요."
        elif risk_score >= 35:
            state = "normal"
            label = "주의"
            color_code = "#FBC02D"
            level = "보통"
            status_text = "약간의 감정 기복이나 평소와 다른 발화 패턴이 존재합니다."
        else:
            if latest_log.llm_summary:
                description = latest_log.llm_summary

        formatted_time = latest_log.created_at.strftime('%p %I:%M')
        time_label = f"오늘 {formatted_time.replace('AM', '오전').replace('PM', '오후')}"
        duration_label = "AI와 대화 완료"

    # 6. [실데이터 연동] Alert 테이블에서 최근 알림 데이터 3개 조회
    db_alerts = db.query(Alert).filter(
        Alert.dependent_id == user_id
    ).order_by(Alert.created_at.desc()).limit(3).all()

    recent_alerts = []
    # 데이터베이스의 알림 타입을 프론트엔드 UI 컴포넌트 형식 명세로 변환
    trigger_type_map = {
        "AI_RISK": {"content": "위험도 기복이 감지되었습니다.", "type": "warning"},
        "EMERGENCY": {"content": "어르신의 도움 요청이 접수되었습니다.", "type": "warning"},
        "INACTIVITY": {"content": "장시간 어르신의 움직임이 감지되지 않았습니다.", "type": "warning"},
    }

    for idx, alert in enumerate(db_alerts, start=1):
        # 맵에 정의되지 않은 타입일 경우 기본 포맷팅 처리
        alert_spec = trigger_type_map.get(
            alert.trigger_type, 
            {"content": f"알림이 발생했습니다. ({alert.trigger_type})", "type": "info"}
        )
        
        # 일기가 공유된 특수 케이스에 대한 유연한 메시지 분기 처리
        content = alert_spec["content"]
        if alert.trigger_type == "AI_RISK" and alert.status == "RESOLVED":
            content = "오늘 일기가 안정적으로 공유되었습니다."
            alert_spec["type"] = "success"

        recent_alerts.append({
            "id": idx,
            "content": content,
            "time_ago": alert.created_at.strftime('%H:%M') if alert.created_at else "방금 전",
            "type": alert_spec["type"]
        })

    # 대화 기록이 아예 없고 생성된 알림도 없는 경우를 위한 최소 방어선 구축
    if not recent_alerts:
        recent_alerts.append({
            "id": 1,
            "content": "공유된 최신 알림 및 특이사항이 존재하지 않습니다.",
            "time_ago": "-",
            "type": "success"
        })

    # 7. 최종 데이터 결합
    dashboard_data = {
        "guardian_name": current_user.name if current_user.name else "가족",
        "senior": {
            "name": dependent.name,
            "status": "연동 중"
        },
        "today_condition": {
            "state": state,
            "label": label,
            "description": description,
            "color_code": color_code
        },
        "risk_assessment": {
            "score": risk_score,
            "level": level,
            "status_text": status_text
        },
        "last_interaction": {
            "time_label": time_label,
            "duration_label": duration_label
        },
        "recent_alerts": recent_alerts
    }

    return unified_response(
        status_code=200,
        message="Dashboard data fetched successfully.",
        data=dashboard_data
    )


@router.get("/{guardian_id}/diary")
def get_diary_detail(
    guardian_id: str = Path(..., description="보호자 고유 ID"),
    user_id: str = Query(..., description="어르신 고유 ID"),
    date: str = Query(..., description="조회 기준 날짜 (YYYY-MM-DD)"),
    current_user: Guardian = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. 권한 검증
    if str(current_user.id) != guardian_id:
        return unified_response(status_code=403, error="접근 권한이 없습니다.")

    # 2. 날짜 파싱
    try:
        target_date = datetime.strptime(date[:10], "%Y-%m-%d").date()
    except ValueError:
        return unified_response(status_code=400, error="잘못된 날짜 형식입니다. (YYYY-MM-DD)")

    # 3. 해당 날짜의 최신 로그 조회
    log = db.query(Log).filter(
        Log.dependent_id == user_id,
        func.date(Log.created_at) == target_date
    ).order_by(Log.created_at.desc()).first()

    if not log:
        return unified_response(status_code=200, message="해당 날짜의 일기 기록이 없습니다.", data=None)

    # 4. 데이터 가공
    # DB에 키워드 컬럼이 별도로 없다면, 임시로 감정이나 기본 키워드를 내려주거나 
    # 추후 LLM 요약 시 키워드를 JSON 형태로 저장하도록 개선할 수 있습니다.
    diary_data = {
        "log_id": log.id,
        "date": target_date.strftime("%Y-%m-%d"),
        "image_url": log.file_url if log.file_url else "기본_이미지_URL", 
        "primary_emotion": log.primary_emotion or "알 수 없음",
        "stt_text": log.stt_text,       # 어르신이 하신 말씀
        "reply_text": log.reply_text,   # AI의 답변
        "summary": log.llm_summary,     # AI 전체 요약
        "keywords": ["대화", log.primary_emotion] if log.primary_emotion else ["일상"]
    }

    return unified_response(status_code=200, data=diary_data)

@router.get("/{guardian_id}/analysis")
def get_risk_analysis(
    guardian_id: str = Path(..., description="보호자 고유 ID"),
    user_id: str = Query(..., description="어르신 고유 ID"),
    db: Session = Depends(get_db),
    current_user: Guardian = Depends(get_current_user)
):
    if str(current_user.id) != guardian_id:
        return unified_response(status_code=403, error="접근 권한이 없습니다.")

    # 최근 7일 기간 설정
    end_date = dt_date.today()
    start_date = end_date - timedelta(days=6)

    # 최근 7일 치의 로그 데이터 조회 (날짜별로 오름차순)
    logs = db.query(Log).filter(
        Log.dependent_id == user_id,
        func.date(Log.created_at) >= start_date,
        func.date(Log.created_at) <= end_date
    ).order_by(Log.created_at.asc()).all()

    # 프론트엔드 차트용 데이터 조립
    # 날짜별로 그룹화하여 가장 높은 점수 또는 최신 점수를 가져오는 로직 (여기서는 단순 반복 처리)
    trend_data = []
    current_date = start_date

    # 7일 치 빈 데이터 뼈대 만들기 (기록이 없는 날도 차트에 빈 구간으로 표시하기 위함)
    date_map = {}
    while current_date <= end_date:
        date_map[current_date.strftime("%m.%d")] = 0.0 # 기본 점수 0
        current_date += timedelta(days=1)

    # 실제 DB 로그 점수로 덮어쓰기 (하루에 여러 번 대화했다면 마지막 대화 점수로 덮어씌워짐)
    for log in logs:
        log_date_str = log.created_at.strftime("%m.%d")
        date_map[log_date_str] = log.risk_score

    # 차트에 넣기 좋은 리스트 형태로 변환
    for date_str, score in date_map.items():
        trend_data.append({
            "date": date_str,
            "score": score
        })

    # AI 주치의 소견 생성 (간단한 룰베이스 예시)
    avg_score = sum(date_map.values()) / 7 if sum(date_map.values()) > 0 else 0
    if avg_score >= 50:
        insight = "최근 일주일간 우울감 또는 인지 저하 징후 수치가 높게 유지되고 있습니다. 각별한 주의와 안부 전화가 필요합니다."
    elif avg_score >= 20:
        insight = "전반적으로 안정적이나, 간헐적으로 감정 기복이 관찰됩니다."
    else:
        insight = "최근 일주일 대비 발화 속도와 어휘 다양성이 매우 안정적입니다."

    analysis_data = {
        "trend_data": trend_data,
        "average_score": round(avg_score, 1),
        "insight": insight
    }

    return unified_response(status_code=200, data=analysis_data)

@router.get("/{guardian_id}/diary/monthly")
def get_monthly_diary_dates(
    guardian_id: str,
    user_id: str = Query(..., description="조회할 어르신의 ID"),
    month: str = Query(..., description="조회할 연월 (예: 2026-06)"),
    db: Session = Depends(get_db),
    current_user: Guardian = Depends(get_current_user)
):
    """
    선택한 월(YYYY-MM)에 그림일기가 작성된 날짜(YYYY-MM-DD) 목록을 반환합니다.
    프론트엔드 달력에 '기록 있는 날' 점(Dot)을 찍기 위한 용도입니다.
    """
    # 1. 보호자와 어르신 간의 연동(매핑) 및 상태(CONNECTED) 확인
    mapping = db.query(GuardianDependentMapping).filter(
        GuardianDependentMapping.guardian_id == current_user.id,
        GuardianDependentMapping.dependent_id == user_id,
        GuardianDependentMapping.status == "CONNECTED"
    ).first()

    if not mapping:
        return unified_response(
            status_code=403,
            error="해당 어르신에 대한 접근 권한이 없거나 아직 연동이 수락되지 않았습니다."
        )

    # 2. 조회할 월의 시작일과 종료일 계산 (예: 2026-06-01 00:00:00 ~ 2026-06-30 23:59:59)
    try:
        target_year, target_month = map(int, month.split('-'))
        # calendar.monthrange는 해당 월의 (시작 요일, 말일)을 튜플로 반환합니다.
        last_day = calendar.monthrange(target_year, target_month)[1]
        
        start_date = datetime(target_year, target_month, 1, 0, 0, 0)
        end_date = datetime(target_year, target_month, last_day, 23, 59, 59)
    except ValueError:
        return unified_response(
            status_code=400,
            error="잘못된 날짜 형식입니다. YYYY-MM 형태로 입력해주세요."
        )

    # 3. Log 테이블의 created_at 컬럼을 기준으로 범위 검색
    # (이미지가 생성된 완료 건만 점을 찍고 싶다면 Log.status == "COMPLETED" 조건을 추가해도 좋습니다)
    logs = db.query(Log.created_at).filter(
        Log.dependent_id == user_id,
        Log.created_at >= start_date,
        Log.created_at <= end_date
    ).all()

    # 4. DateTime 객체에서 'YYYY-MM-DD' 형태의 문자열만 추출 후 중복 제거
    # logs는 [(datetime.datetime(...),), (datetime.datetime(...),)] 형태입니다.
    written_dates = list(set([log[0].strftime("%Y-%m-%d") for log in logs if log[0]]))
    
    # 날짜순으로 정렬
    written_dates.sort()

    return unified_response(
        status_code=200,
        message="Monthly diary dates retrieved successfully.",
        data=written_dates
    )

