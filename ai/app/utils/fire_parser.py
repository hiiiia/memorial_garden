# ai/utils/file_parser.py
import os
import httpx
import tempfile

# 도커 공유 볼륨 마운트 경로 (docker-compose.yml 기준)
SHARED_UPLOAD_DIR = "/app/uploads"

async def prepare_audio_file(file_url: str) -> str:
    """
    URL (local:// vs http://)을 분석하여, 
    AI 모델이 읽을 수 있는 로컬 파일 경로를 반환합니다.
    """
    
    # ---------------------------------------------------------
    # CASE 1: 로컬 공유 볼륨 (네트워크 전송 없이 바로 읽기)
    # ---------------------------------------------------------
    if file_url.startswith("local://"):
        # URL에서 'local://'을 제거하여 상대 경로 추출 (예: 20260528/abc.wav)
        relative_path = file_url.replace("local://", "")
        
        # 공유 폴더의 절대 경로와 결합
        local_path = os.path.join(SHARED_UPLOAD_DIR, relative_path)
        
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"공유 폴더에서 파일을 찾을 수 없습니다: {local_path}")
            
        print(f"[AI Server] 공유 볼륨에서 파일을 직접 읽습니다: {local_path}")
        return local_path
        
    # ---------------------------------------------------------
    # CASE 2: 상용 클라우드 스토리지 (S3, Firebase 등에서 다운로드)
    # ---------------------------------------------------------
    elif file_url.startswith("http://") or file_url.startswith("https://"):
        # 시스템의 임시 폴더(tmp) 경로 가져오기
        temp_dir = tempfile.gettempdir()
        filename = file_url.split("/")[-1]
        temp_path = os.path.join(temp_dir, f"dl_{filename}")
        
        print(f"[AI Server] 클라우드 스토리징에서 파일을 다운로드합니다: {file_url}")
        
        # 비동기로 파일 다운로드
        async with httpx.AsyncClient() as client:
            response = await client.get(file_url)
            response.raise_for_status()
            
            with open(temp_path, "wb") as f:
                f.write(response.content)
                
        return temp_path
        
    # ---------------------------------------------------------
    # 예외 처리: 알 수 없는 포맷
    # ---------------------------------------------------------
    else:
        raise ValueError(f"지원하지 않는 파일 URL입니다: {file_url}")