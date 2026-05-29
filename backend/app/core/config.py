# core/config.py
import os
from urllib.parse import quote_plus

class Settings:
    # 프로젝트 메타데이터
    PROJECT_NAME: str = "AI 정서 케어 플랫폼 API"
    PROJECT_VERSION: str = "1.0.0"

    # 데이터베이스 설정 (Docker 환경변수 주입을 위해 os.getenv 사용)
    # 기본값 'db'는 docker-compose.yml의 데이터베이스 서비스 이름과 맞추면 됩니다.
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "password")
    DB_HOST: str = os.getenv("DB_HOST", "db") 
    DB_PORT: str = os.getenv("DB_PORT", "3306")
    DB_NAME: str = os.getenv("DB_NAME", "aicare")

    # DB 연결 URL 자동 조합
    DATABASE_URL: str = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    # AI 중계 서버 주소 불러오기 ⭐️
    AI_PROXY_URL: str = os.getenv("AI_PROXY_URL", "http://ai:8001")

    

    # JWT 보안 설정 (이후 로그인 구현 시 사용)
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-key-for-dev")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1일
    
    # 특수문자 방어용 비밀번호 인코딩
    SAFE_PASSWORD = quote_plus(DB_PASSWORD)
    
    API_SECRET_TOKEN: str = os.getenv("API_SECRET_TOKEN","default-token")
    AI_SECRET_TOKEN: str = os.getenv("AI_SECRET_TOKEN", "default-token")
    OPENAI_API_KEY : str = os.getenv("OPENAI_API_KEY", "default-token")

# 인스턴스화하여 다른 파일에서 쉽게 임포트하도록 함
settings = Settings()