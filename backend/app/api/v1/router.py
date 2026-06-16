# C:\Users\User\Documents\memorial_garden\backend\app\api\v1\router.py
from fastapi import APIRouter
from api.v1 import health
from api.v1.callbacks import jobs
from api.v1.files import files
#from api.v1.utils import 
from api.v1.auth import auth
from api.v1.dashboard import dashboard
from api.v1.guardians import guardians
from api.v1.dependents import dependents
from api.v1.memory import rag

# v1 전용 통합 라우터 생성
api_router = APIRouter()

# 1. 파일 관련 라우터 (/api/v1/files/...)
api_router.include_router(files.router, prefix="/files", tags=["Files"])

# 2. 헬스 체크 라우터 (/api/v1/health)
api_router.include_router(health.router,prefix="/health", tags=["System"])

# 3. 콜백 관련 라우터 (/api/v1/callbacks/jobs/...)
api_router.include_router(jobs.router, prefix="/callbacks/jobs", tags=["Callbacks"])

# 4. 기능 관련 라우터 (/api/v1/utils/...)
#api_router.include_router(jobs.router, prefix="/utils", tags=["utils"])

# 5. 인증 관련 라우터 (/api/v1/auth/...)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])

api_router.include_router(guardians.router, prefix="/guardian", tags=["Guardian"])

api_router.include_router(dependents.router, prefix="/dependent", tags=["dependent"])

# RAG 라우터
api_router.include_router(rag.router, prefix="/memory", tags=["Memory"])
