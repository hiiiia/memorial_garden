from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime, date as dt_date, timedelta
import calendar
from typing import Optional

# 기존 임포트 경로 유지
from api.v1.deps import get_current_user
from db.database import get_db
from db.models import Guardian, Dependent, GuardianDependentMapping, Log, Alert
from core.response import unified_response

router = APIRouter()

# ==========================================
# 1. 보호자 메인 대시보드 요약 정보 조회
# ==========================================
@router.get("")
def get_guardian_dashboard(
    user_id: str = Query(..., description="어르신 고유 ID"),
    date: Optional[str] = Query(None, description="조회 기준 날짜 (ISO String 또는 YYYY-MM-DD)"),
    current_user: Guardian = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    [로그인 전용] 현재 대화 상태, 위험도 점수 및 실시간 최근 알림 3개를 결합한 메인 대시보드 데이터를 반환합니다.
    URL에서 guardian_id를 제거하고 토큰 기반으로 검증하여 안전합니다.
    """
    # 1. 보호자-어르신 연동 관계 및 상태 확인
    mapping = db.query(GuardianDependentMapping).filter(
        GuardianDependentMapping.guardian_id == current_user.id,
        GuardianDependentMapping.dependent_id == user_id
    ).first()

    if not mapping:
        raise HTTPException(status_code=404, detail="연동 정보가 존재하지 않습니다. 어르신을 먼저 등록해주세요.")

    # 어르신 측 수락 대기 상태(PENDING) 처리 - 프론트엔드 명세에 맞춤
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
        raise HTTPException(status_code=400, detail="어르신에 의해 연동 요청이 거절되었습니다.")

    # 2. 어르신 정보 조회
    dependent = db.query(Dependent).filter(Dependent.id == user_id).first()
    if not dependent:
        raise HTTPException(status_code=404, detail="어르신 정보를 찾을 수 없습니다.")

    # 3. 날짜 파싱 및 해당 날짜의 최신 로그(Log) 조회
    if date:
        try:
            target_date = datetime.fromisoformat(date.replace("Z", "")).date()
        except ValueError:
            target_date = datetime.strptime(date[:10], "%Y-%m-%d").date()
    else:
        target_date = dt_date.today()

    latest_log = db.query(Log).filter(
        Log.dependent_id == user_id,
        Log.status == "COMPLETED",
        func.date(Log.created_at) == target_date
    ).order_by(Log.created_at.desc()).first()

    last_completed_log = latest_log or db.query(Log).filter(
        Log.dependent_id == user_id,
        Log.status == "COMPLETED"
    ).order_by(Log.created_at.desc()).first()

    # 4. 프론트엔드 포맷 초기화 (기본값 설정)
    state = "good"
    label = "안정"
    description = "오늘 진행된 대화가 없거나 특이사항이 없습니다."
    color_code = "#388E3C"
    risk_score = 0
    level = "낮음"
    status_text = "안정적인 상태입니다."
    time_label = "대화 기록 없음"
    duration_label = "라즈베리파이 연결 상태를 확인하세요."
    interaction_summary = "대화 기록 없음"

    if latest_log:
        risk_score = int((latest_log.risk_score or 0) * 100) if latest_log.risk_score <= 1.0 else int(latest_log.risk_score)
        
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

    if last_completed_log:
        formatted_time = last_completed_log.created_at.strftime('%p %I:%M')
        localized_time = formatted_time.replace('AM', '오전').replace('PM', '오후')
        if last_completed_log.created_at.date() == dt_date.today():
            time_label = f"오늘 {localized_time}"
        else:
            time_label = f"{last_completed_log.created_at.strftime('%Y-%m-%d')} {localized_time}"
        duration_label = "AI와 대화 완료"
        interaction_summary = last_completed_log.llm_summary or "대화 요약이 없습니다."

    # 5. Alert 테이블에서 최근 알림 데이터 3개 조회
    db_alerts = db.query(Alert).filter(
        Alert.dependent_id == user_id
    ).order_by(Alert.created_at.desc()).limit(3).all()

    recent_alerts = []
    trigger_type_map = {
        "AI_RISK": {"content": "위험도 기복이 감지되었습니다.", "type": "warning"},
        "EMERGENCY": {"content": "어르신의 도움 요청이 접수되었습니다.", "type": "warning"},
        "INACTIVITY": {"content": "장시간 어르신의 움직임이 감지되지 않았습니다.", "type": "warning"},
    }

    for idx, alert in enumerate(db_alerts, start=1):
        alert_spec = trigger_type_map.get(
            alert.trigger_type, 
            {"content": f"알림이 발생했습니다. ({alert.trigger_type})", "type": "info"}
        )
        
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

    if not recent_alerts:
        recent_alerts.append({
            "id": 1,
            "content": "공유된 최신 알림 및 특이사항이 존재하지 않습니다.",
            "time_ago": "-",
            "type": "success"
        })

    # 6. 최종 대시보드 데이터 결합 및 반환
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
            "duration_label": duration_label,
            "summary": interaction_summary
        },
        "recent_alerts": recent_alerts
    }

    return unified_response(
        status_code=200,
        message="Dashboard data fetched successfully.",
        data=dashboard_data
    )


# ==========================================
# 2. 특정 날짜의 그림일기 상세 조회
# ==========================================
@router.get("/diary")
def get_diary_detail(
    user_id: str = Query(..., description="어르신 고유 ID"),
    date: str = Query(..., description="조회 기준 날짜 (YYYY-MM-DD)"),
    current_user: Guardian = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    [로그인 전용] 특정 날짜를 클릭했을 때 대화 원본 스크립트와 AI 소견, 그림일기를 상세 조회합니다.
    """
    # 1. 권한 검증 (매핑 확인)
    mapping = db.query(GuardianDependentMapping).filter(
        GuardianDependentMapping.guardian_id == current_user.id,
        GuardianDependentMapping.dependent_id == user_id,
        GuardianDependentMapping.status == "CONNECTED"
    ).first()

    if not mapping:
        raise HTTPException(status_code=403, detail="접근 권한이 없거나 연동 완료 상태가 아닙니다.")

    # 2. 날짜 파싱
    try:
        target_date = datetime.strptime(date[:10], "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="잘못된 날짜 형식입니다. (YYYY-MM-DD)")

    # 3. 해당 날짜의 최신 완료 로그 조회
    log = db.query(Log).filter(
        Log.dependent_id == user_id,
        Log.status == "COMPLETED",
        func.date(Log.created_at) == target_date
    ).order_by(Log.created_at.desc()).first()

    if not log:
        return unified_response(status_code=200, message="해당 날짜의 일기 기록이 없습니다.", data=None)

    # 4. 해시태그(Keywords) 파싱 로직
    kw_list = []
    if log.keywords:
        kw_list = [k.strip() for k in log.keywords.split(",") if k.strip()]
    else:
        kw_list = ["일상", log.primary_emotion or "평온"]

    # 5. 새로 추가된 DB 명세 기반 데이터 매핑
    diary_data = {
        "log_id": log.id,
        "date": target_date.strftime("%Y-%m-%d"),
        "image_url": log.image_url if log.image_url else "https://via.placeholder.com/800x400?text=No+Image",
        "primary_emotion": log.primary_emotion or "보통",
        "stt_text": "",       # 어르신 발화
        "reply_text": "",   # AI 답변
        "diary_text": log.diary_text or log.llm_summary, # 동화풍 그림일기 내용 본문
        "summary": log.llm_summary,     # 임상 분석용 내부 요약
        "keywords": kw_list
    }

    return unified_response(status_code=200, data=diary_data)


# ==========================================
# 3. 최근 7일간 마음 건강 주간 위험도 분석 조회
# ==========================================
@router.get("/analysis")
def get_risk_analysis(
    user_id: str = Query(..., description="어르신 고유 ID"),
    db: Session = Depends(get_db),
    current_user: Guardian = Depends(get_current_user)
):
    """
    [로그인 전용] 보호자 페이지의 꺾은선 차트 연동용 API입니다. 일주일간의 추세를 계산합니다.
    """
    mapping = db.query(GuardianDependentMapping).filter(
        GuardianDependentMapping.guardian_id == current_user.id,
        GuardianDependentMapping.dependent_id == user_id
    ).first()

    if not mapping:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다.")

    # 최근 7일 기간 설정
    end_date = dt_date.today()
    start_date = end_date - timedelta(days=6)

    logs = db.query(Log).filter(
        Log.dependent_id == user_id,
        Log.status == "COMPLETED",
        func.date(Log.created_at) >= start_date,
        func.date(Log.created_at) <= end_date
    ).order_by(Log.created_at.asc()).all()

    # 뼈대 생성 (공백 방지)
    trend_data = []
    current_date = start_date
    date_map = {}
    
    while current_date <= end_date:
        date_map[current_date.strftime("%m.%d")] = 0.0
        current_date += timedelta(days=1)

    # 실제 DB 로그 점수로 오버라이드
    for log in logs:
        log_date_str = log.created_at.strftime("%m.%d")
        # 0.0~1.0 범위를 100점 만점으로 변환하여 차트에 대응
        raw_score = log.risk_score or 0.0
        date_map[log_date_str] = int(raw_score * 100) if raw_score <= 1.0 else int(raw_score)

    for date_str, score in date_map.items():
        trend_data.append({
            "date": date_str,
            "score": score
        })

    # 종합 평균 기반 규칙 주치의 소견 생성
    # 일기가 없는 날은 평균 계산에서 제외
    valid_scores = []

    for log in logs:
        if log.diary_text and log.diary_text.strip():
            raw_score = log.risk_score or 0.0
            score = int(raw_score * 100) if raw_score <= 1.0 else int(raw_score)
            valid_scores.append(score)

    avg_score = (
        sum(valid_scores) / len(valid_scores)
        if valid_scores
        else 0
    )

    if avg_score >= 60:
        insight = "최근 일주일간 마음 불안정 및 인지 기복 수치가 다소 높게 관찰됩니다. 오늘 저녁에는 따뜻한 안부 전화를 드려 심리적 안정감을 높여주시는 것을 권장합니다."
    elif avg_score >= 30:
        insight = "전반적으로 규칙적인 생활 패턴을 유지하고 계시나, 간헐적인 감정 기복이 파악됩니다."
    else:
        insight = "어르신의 발화 어휘 다양성과 감정 상태가 정서적으로 매우 안정된 이상적인 곡선을 유지하고 있습니다."

    analysis_data = {
        "trend_data": trend_data,
        "average_score": round(avg_score, 1),
        "insight": insight
    }

    return unified_response(status_code=200, data=analysis_data)


# ==========================================
# 4. 리액트 달력 UI 전용 월별 데이터 일괄 조회
# ==========================================
@router.get("/diary/monthly")
def get_monthly_diary_payload(
    user_id: str = Query(..., description="조회할 어르신의 ID"),
    month: str = Query(..., description="조회할 연월 (예: 2026-06)"),
    db: Session = Depends(get_db),
    current_user: Guardian = Depends(get_current_user)
):
    """
    [달력 전용 핵심 API] 선택한 연월(YYYY-MM)의 전체 완료 일기와 건강 보고서를 통째로 긁어옵니다.
    프론트엔드 달력의 점(Dot) 마킹 및 일기장/건강 탭 스위칭 컴포넌트 데이터 공급을 단 한 번의 호출로 해결합니다.
    """
    # 1. 권한 검증
    mapping = db.query(GuardianDependentMapping).filter(
        GuardianDependentMapping.guardian_id == current_user.id,
        GuardianDependentMapping.dependent_id == user_id,
        GuardianDependentMapping.status == "CONNECTED"
    ).first()

    if not mapping:
        raise HTTPException(status_code=403, detail="해당 어르신에 대한 접근 권한이 없거나 연동이 수락되지 않았습니다.")

    # 2. 조회할 월의 경계값 계산
    try:
        target_year, target_month = map(int, month.split('-'))
        last_day = calendar.monthrange(target_year, target_month)[1]
        
        start_date = datetime(target_year, target_month, 1, 0, 0, 0)
        end_date = datetime(target_year, target_month, last_day, 23, 59, 59)
    except ValueError:
        raise HTTPException(status_code=400, detail="잘못된 날짜 형식입니다. YYYY-MM 형태로 입력해주세요.")

    # 3. 한 달치 데이터 일괄 쿼리
    logs = db.query(Log).filter(
        Log.dependent_id == user_id,
        Log.status == "COMPLETED",
        Log.created_at >= start_date,
        Log.created_at <= end_date
    ).order_by(Log.created_at.asc()).all()

    # 4. 프론트엔드 달력 상태(`MainPage.tsx`)에 정확히 호환되도록 포맷팅
    diary_list = []
    health_list = []

    for log in logs:
        # 리액트 달력 매칭용 YYYY-MM-DD 포맷팅
        log_date_str = log.created_at.strftime("%Y-%m-%d")

        # 해시태그 가공
        kw_list = []
        if log.keywords:
            kw_list = [k.strip() for k in log.keywords.split(",") if k.strip()]
        else:
            kw_list = ["일상", log.primary_emotion or "안정"]

        raw_risk = log.risk_score or 0.0
        risk_score = int(raw_risk * 100) if raw_risk <= 1.0 else int(raw_risk)

        # 📖 1. 일기 탭 데이터 적재
        diary_list.append({
            "id": log.id,
            "date": log_date_str,
            "imageUrl": log.image_url or "https://via.placeholder.com/800x400?text=No+Image",
            "content": log.diary_text or log.llm_summary or "기록된 일기가 없습니다.",
            "keywords": kw_list,
            "riskScore": risk_score
        })

        # 🩺 2. 건강 보고서 탭 데이터 적재 (Float 점수 -> 0~100 정수 스케일링 적용)
        raw_dep = log.depression_score or 0.0
        raw_cog = log.cognitive_decline_score or 0.0

        health_list.append({
            "id": log.id,
            "date": log_date_str,
            "depressionScore": int(raw_dep * 100) if raw_dep <= 1.0 else int(raw_dep),
            "dementiaScore": int(raw_cog * 100) if raw_cog <= 1.0 else int(raw_cog),
            "insight": log.llm_summary or "안정적인 대화 패턴이 유지되고 있습니다."
        })

    # 5. 완성된 월간 패키지 응답 반환
    return unified_response(
        status_code=200,
        message="Monthly calendar package retrieved successfully.",
        data={
            "diary_list": diary_list,
            "health_list": health_list
        }
    )
