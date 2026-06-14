from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from db import models

MEMORY_CONFIDENCE_THRESHOLD = 0.6
MEMORY_CONTEXT_LIMIT = 50

MOCK_MEMORY_TEST_CASES = [
    {
        "name": "same_son_name_seen_count_increment",
        "previous_memory": {
            "category": "family",
            "key": "아들 이름",
            "value": "김개똥",
            "confidence": 0.9,
            "seen_count": 1,
        },
        "current_speech": "아들 김개똥이가 왔다",
        "expected": "memory_profile_updates seen_count 증가, memory_conflicts 없음",
    },
    {
        "name": "different_son_name_conflict",
        "previous_memory": {
            "category": "family",
            "key": "아들 이름",
            "value": "김개똥",
            "confidence": 0.9,
            "seen_count": 1,
        },
        "current_speech": "아들 박길동이가 왔다",
        "expected": "memory_conflicts 생성, cognitive_decline_score 상승 가능",
    },
    {
        "name": "meaningless_test_speech_no_memory",
        "previous_memory": None,
        "current_speech": "테스트 하나 둘 셋",
        "expected": "memory_profile_updates 빈 배열, memory_conflicts 빈 배열",
    },
]


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_importance(value: Any) -> str:
    importance = _clean_text(value).upper()
    if importance in {"HIGH", "MEDIUM", "LOW"}:
        return importance
    return "MEDIUM"


def _normalize_severity(value: Any) -> str:
    severity = _clean_text(value).upper()
    if severity in {"INFO", "WATCH", "WARNING", "EMERGENCY"}:
        return severity
    return "WATCH"


def _to_dict(item: Any) -> Dict[str, Any]:
    if hasattr(item, "model_dump"):
        return item.model_dump()
    if hasattr(item, "dict"):
        return item.dict()
    if isinstance(item, dict):
        return item
    return {}


def build_memory_profile_context(db: Session, user_id: str, limit: int = MEMORY_CONTEXT_LIMIT) -> List[Dict[str, Any]]:
    profiles = (
        db.query(models.MemoryProfile)
        .filter(
            models.MemoryProfile.user_id == user_id,
            models.MemoryProfile.is_active == True,
        )
        .order_by(models.MemoryProfile.importance.desc(), models.MemoryProfile.seen_count.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "category": profile.category,
            "key": profile.key,
            "value": profile.value,
            "confidence": profile.confidence,
            "seen_count": profile.seen_count,
        }
        for profile in profiles
    ]


def _has_conflict_payload(conflicts: List[Dict[str, Any]], category: str, key: str, current_value: str) -> bool:
    return any(
        _clean_text(conflict.get("category")) == category
        and _clean_text(conflict.get("key")) == key
        and _clean_text(conflict.get("current_value")) == current_value
        for conflict in conflicts
    )


def create_memory_conflict(
    db: Session,
    user_id: str,
    category: str,
    key: str,
    previous_value: str,
    current_value: str,
    source_text: Optional[str] = None,
    severity: str = "WATCH",
    note: Optional[str] = None,
) -> models.MemoryConflict:
    conflict = models.MemoryConflict(
        user_id=user_id,
        category=category,
        key=key,
        previous_value=previous_value,
        current_value=current_value,
        source_text=source_text,
        severity=_normalize_severity(severity),
        note=note,
    )
    db.add(conflict)
    return conflict


def save_memory_profile_updates(db: Session, user_id: str, updates: List[Any], conflicts: List[Any]) -> None:
    normalized_conflicts = [_to_dict(conflict) for conflict in conflicts]

    for raw_update in updates:
        update = _to_dict(raw_update)
        category = _clean_text(update.get("category"))
        key = _clean_text(update.get("key"))
        value = _clean_text(update.get("value"))
        source_text = _clean_text(update.get("source_text")) or None
        importance = _normalize_importance(update.get("importance"))

        try:
            confidence = float(update.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0

        if not category or not key or not value or confidence < MEMORY_CONFIDENCE_THRESHOLD:
            continue

        existing_same_value = (
            db.query(models.MemoryProfile)
            .filter(
                models.MemoryProfile.user_id == user_id,
                models.MemoryProfile.category == category,
                models.MemoryProfile.key == key,
                models.MemoryProfile.value == value,
                models.MemoryProfile.is_active == True,
            )
            .first()
        )

        if existing_same_value:
            existing_same_value.seen_count += 1
            existing_same_value.last_seen_at = datetime.utcnow()
            existing_same_value.confidence = max(existing_same_value.confidence or 0.0, confidence)
            existing_same_value.importance = importance
            existing_same_value.source_text = source_text or existing_same_value.source_text
            continue

        existing_other_value = (
            db.query(models.MemoryProfile)
            .filter(
                models.MemoryProfile.user_id == user_id,
                models.MemoryProfile.category == category,
                models.MemoryProfile.key == key,
                models.MemoryProfile.is_active == True,
            )
            .first()
        )

        if existing_other_value:
            if not _has_conflict_payload(normalized_conflicts, category, key, value):
                create_memory_conflict(
                    db=db,
                    user_id=user_id,
                    category=category,
                    key=key,
                    previous_value=existing_other_value.value,
                    current_value=value,
                    source_text=source_text,
                    severity="WATCH",
                    note="기존 장기기억 프로필과 현재 발화의 값이 다릅니다.",
                )
            continue

        db.add(
            models.MemoryProfile(
                user_id=user_id,
                category=category,
                key=key,
                value=value,
                confidence=confidence,
                importance=importance,
                source_text=source_text,
                seen_count=1,
                is_active=True,
            )
        )


def save_memory_conflicts(db: Session, user_id: str, conflicts: List[Any]) -> None:
    for raw_conflict in conflicts:
        conflict = _to_dict(raw_conflict)
        category = _clean_text(conflict.get("category"))
        key = _clean_text(conflict.get("key"))
        previous_value = _clean_text(conflict.get("previous_value"))
        current_value = _clean_text(conflict.get("current_value"))

        if not category or not key or not previous_value or not current_value:
            continue

        create_memory_conflict(
            db=db,
            user_id=user_id,
            category=category,
            key=key,
            previous_value=previous_value,
            current_value=current_value,
            source_text=_clean_text(conflict.get("source_text")) or None,
            severity=_normalize_severity(conflict.get("severity")),
            note=_clean_text(conflict.get("note")) or None,
        )


def save_memory_analysis(db: Session, user_id: str, updates: List[Any], conflicts: List[Any]) -> None:
    save_memory_profile_updates(db, user_id, updates or [], conflicts or [])
    save_memory_conflicts(db, user_id, conflicts or [])
