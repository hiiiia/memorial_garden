# config.py
import os

class Settings:
    # 도커 환경변수에서 값을 가져오고, 없으면 기본값을 세팅합니다.
    AI_SERVER_URL: str = os.getenv("AI_SERVER_URL", "http://192.168.1.82:8001")
    DEPENDENT_ID: str = os.getenv("DEPENDENT_ID", "dep_003")
    BACKEND_URL : str = os.getenv("BACKEND_URL", "http://192.168.1.82:8000")
    
    # Bearer 글자는 제외하고 순수 토큰 값만 환경변수로 관리하는 것이 깔끔합니다.
    HW_TOKEN: str = os.getenv("HW_TOKEN", "default-token")

settings = Settings()