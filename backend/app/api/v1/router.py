# C:\Users\User\Documents\memorial_garden\backend\app\api\v1\router.py
from fastapi import APIRouter
from api.v1 import health
from api.v1.callbacks import jobs
from api.v1.files import files

# v1 전용 통합 라우터 생성
api_router = APIRouter()

# 1. 파일 관련 라우터 (/api/v1/files/...)
api_router.include_router(files.router, prefix="/files", tags=["Files"])

# 2. 헬스 체크 라우터 (/api/v1/health)
api_router.include_router(health.router,prefix="/health", tags=["System"])

# 3. 콜백 관련 라우터 (/api/v1/callbacks/jobs/...)
api_router.include_router(jobs.router, prefix="/callbacks/jobs", tags=["Callbacks"])