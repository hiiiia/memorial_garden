# core/storage.py
import os
import shutil
import uuid
from datetime import datetime
from fastapi import UploadFile, Request

# 도커 저장 디렉토리 {root}\shared_uploads  : {root}\backend\app\uploads
UPLOAD_DIR = "/app/uploads"

####### URL으로 전달하는 방식
# async def save_file_and_get_url(file: UploadFile, request: Request) -> str:
#     """
#     업로드된 파일을 저장하고 외부에서 접근 가능한 URL을 반환합니다.
#     (나중에 클라우드 스토리지로 변경 시 이 내부 로직만 S3/Firebase 코드로 교체하면 됩니다.)
#     """
#     today_str = datetime.utcnow().strftime("%Y%m%d")
#     save_dir = os.path.join(UPLOAD_DIR, today_str)
#     os.makedirs(save_dir, exist_ok=True) 

#     safe_filename = f"{uuid.uuid4().hex[:8]}_{file.filename}"
#     file_path = os.path.join(save_dir, safe_filename)

#     # 1. 파일 저장 (현재는 로컬 디스크)
#     with open(file_path, "wb") as buffer:
#         shutil.copyfileobj(file.file, buffer)

#     # 2. 접근 가능한 URL 생성
#     # http://localhost:8000
#     base_url = str(request.base_url)
#     real_file_url = f"{base_url}static/{today_str}/{safe_filename}"
#     print(real_file_url)
#     return real_file_url


async def save_file_and_get_url(file: UploadFile, request: Request) -> str:
    """
    업로드된 파일을 도커 공유 볼륨에 저장하고, 
    AI 서버가 접근할 수 있는 절대 경로(Absolute Path)를 반환합니다.
    """
    today_str = datetime.utcnow().strftime("%Y%m%d")
    
    # 1. 저장할 폴더 경로 생성 (예: /app/uploads/20260529)
    save_dir = os.path.join(UPLOAD_DIR, today_str)
    os.makedirs(save_dir, exist_ok=True) 

    # 2. 안전한 파일명 생성
    safe_filename = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    
    # 3. 최종 파일 절대 경로 (이 값이 저장 위치이자, 반환값입니다!)
    file_path = os.path.join(save_dir, safe_filename)

    # 4. 파일 저장
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    print(f"[Backend] 파일 저장 완료, AI로 전달할 경로: {file_path}")
    
    # 5. 저장한 절대 경로를 그대로 반환 (static 같은 가짜 폴더명은 쓰지 않습니다)
    return file_path