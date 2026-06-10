# api/v1/utils/backup.py

import os
import json
from datetime import datetime
from typing import Any, Dict

def save_failed_callback_to_local(
    job_id: str, 
    user_id: str, 
    payload: Dict[str, Any], 
    error_reason: str, 
    backup_dir: str = "failed_callbacks"
) -> bool:
    """
    콜백 전송에 실패한 데이터를 로컬 JSON 파일로 안전하게 보관합니다.
    """
    try:
        # 1. 폴더 생성 (없으면 자동 생성)
        os.makedirs(backup_dir, exist_ok=True)
        
        # 2. 타임스탬프를 포함한 고유 파일명 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"failed_job_{job_id}_{timestamp}.json"
        filepath = os.path.join(backup_dir, filename)
        
        # 3. 에러 원인과 원본 데이터를 묶어서 저장할 구조 만들기
        backup_data = {
            "job_id": job_id,
            "user_id": user_id,
            "failed_time": timestamp,
            "error_reason": error_reason,
            "original_payload": payload 
        }
        
        # 4. JSON 파일로 기록
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=4)
            
        print(f"[AI Recovery] ✅ 데이터 로컬 백업 완료! 저장 위치: {filepath}")
        return True
        
    except Exception as e:
        print(f"[AI SYSTEM ALERT] 로컬 백업 저장 실패. 데이터 유실 발생: {str(e)}")
        return False