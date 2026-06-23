# C:\Users\User\Documents\memorial_garden\backend\app\main.py
import os
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from db.database import engine
from db import models
from sqlalchemy.exc import OperationalError

from sqlalchemy.exc import OperationalError
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.response import unified_response
from api.v1.router import api_router 
from api.v1.ws import ws_router


try:
    # 서버 구동 시 DB 테이블 자동 생성
    models.Base.metadata.create_all(bind=engine)
except OperationalError as e:
    # DB가 꺼져있어도 FastAPI 서버 자체는 일단 켜지도록 예외 처리
    print(f"⚠️ [경고] 서버 구동 중 DB 연결에 실패했습니다: {e}")
    
    
# FastAPI 앱 인스턴스 생성
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION
)

# 1. HTTP 에러 팩토리 사용 (StarletteHTTPException 사용)
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    FastAPI에서 발생하는 모든 HTTP 에러(우리가 raise한 것 + 프레임워크 자체 에러)를
    가로채서 unified_response 규격으로 내보냅니다.
    """
    return unified_response(
        status_code=exc.status_code,
        error=exc.detail  # 에러 메시지를 error 필드에
    )

# 2. 파라미터/바디 검증 에러 처리
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # 에러 메시지를 보기 좋게 가공 (예: "body -> user_id: 필드가 누락되었습니다.")
    error_messages = []
    for err in exc.errors():
        loc = " -> ".join([str(l) for l in err["loc"]])
        error_messages.append(f"[{loc}] {err['msg']}")
        
    return unified_response(
        status_code=422,
        error="입력값이 올바르지 않습니다.",
        data={"validation_details": error_messages}
    )

# 3. API 통신 중 발생하는 DB 연결 에러 방어
@app.exception_handler(OperationalError)
async def db_operational_error_handler(request: Request, exc: OperationalError):
    # 서버 콘솔에는 상세 에러를 남겨서 디버깅이 가능하게 합니다.
    print(f"🚨 데이터베이스 연결 오류 발생: {exc}") 
    
    # 클라이언트에게는 민감한 DB 정보(exc)를 숨기고 정형화된 응답만 보냅니다.
    return unified_response(
        status_code=503, # 503 Service Unavailable
        error="데이터베이스 서버와 연결할 수 없거나 응답이 지연되고 있습니다."
    )

# CORS 미들웨어 설정 (반드시 app.include_router 보다 위에 작성)
app.add_middleware(
    CORSMiddleware,
    #allow_origins=settings.ALLOWED_ORIGINS, # 리스트 형태로 깔끔하게 주입
    allow_origins=["*"], # 전체 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# # 1. 절대 경로로 안전하게 폴더 생성 (음성 파일 전용)
# AUDIO_SAVE_DIR = "/app/uploads/shared_audio"
# os.makedirs(AUDIO_SAVE_DIR, exist_ok=True)

# # '/static/audio'로 분리하여 마운트
# app.mount("/static/audio", StaticFiles(directory=AUDIO_SAVE_DIR), name="static_audio")

# 이미지용 마운트
os.makedirs("/app/uploads/diary_images", exist_ok=True)
app.mount("/static/diary_images", StaticFiles(directory="/app/uploads/diary_images"), name="diary_images")


# 라우터 등록 (이 한 줄로 모든 api/v1/... 경로가 활성화됩니다!)
app.include_router(api_router, prefix="/api/v1")

# 어르신 기기 전용 ws
app.include_router(ws_router.ws_router, prefix="/ws", tags=["websocket"])


# 사파리 브라우저 아이콘 요청시 void return
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(content=b"", media_type="image/x-icon")

# (Root Endpoint)
@app.get("/")
def read_root():
    return {"message": "Welcome to Central API Server"}

