import os

class Settings:
    # 프로젝트 메타데이터
    PROJECT_NAME: str = "AI Analysis Server"
    PROJECT_VERSION: str = "1.0.0"

    # 핵심 환경 변수 (Docker의 env_file을 통해 주입됨)
    # 기본값(두 번째 인자)은 혹시라도 .env가 없을 때를 대비한 안전장치입니다.
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")
    
    # 보안 토큰 (백엔드와 통신 시 서로를 인증하는 암구호)
    # 백엔드의 API_SECRET_TOKEN과 똑같은 값을 사용해야 하므로 환경 변수명을 맞춥니다.
    AI_SECRET_TOKEN: str = os.getenv("AI_SECRET_TOKEN", "default-token")

    # 콜백을 보낼 백엔드 서버 주소
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://backend:8000")

# 인스턴스화하여 다른 파일에서 쉽게 임포트하도록 함
settings = Settings()