# core/storage.py
import os
import shutil
import uuid
from datetime import datetime
from fastapi import UploadFile, Request

# 로컬 저장소 최상위 디렉토리
UPLOAD_DIR = os.path.join(os.getcwd(), "shared_uploads")

async def save_file_and_get_url(file: UploadFile, request: Request) -> str:
    """
    업로드된 파일을 저장하고 외부에서 접근 가능한 URL을 반환합니다.
    (나중에 클라우드 스토리지로 변경 시 이 내부 로직만 S3/Firebase 코드로 교체하면 됩니다.)
    """
    today_str = datetime.utcnow().strftime("%Y%m%d")
    save_dir = os.path.join(UPLOAD_DIR, today_str)
    os.makedirs(save_dir, exist_ok=True) 

    safe_filename = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    file_path = os.path.join(save_dir, safe_filename)

    # 1. 파일 저장 (현재는 로컬 디스크)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 2. 접근 가능한 URL 생성
    base_url = str(request.base_url)
    real_file_url = f"{base_url}static/{today_str}/{safe_filename}"

    return real_file_url