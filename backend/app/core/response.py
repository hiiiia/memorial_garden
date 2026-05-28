from typing import TypeVar, Optional, Generic, Any
from pydantic import BaseModel  # 👈 GenericModel 대신 BaseModel 사용
from fastapi.responses import JSONResponse

# 어떤 데이터 구조든 유연하게 수용하기 위한 제네릭 타입 선언
T = TypeVar('T')

# BaseModel과 Generic을 함께 상속받습니다.
class ApiResponse(BaseModel, Generic[T]):
    """
    전체 프로젝트에서 일괄 사용할 공통 응답 스키마 클래스
    """
    code: int                      
    message: Optional[str] = None  
    data: Optional[T] = None       
    error: Optional[str] = None    

    # Pydantic V2 방식: class Config 대신 model_config 딕셔너리 사용
    # schema_extra도 json_schema_extra로 이름이 변경되었습니다.
    model_config = {
        "json_schema_extra": {
            "example": {
                "code": 200,
                "message": "Request processed successfully.",
                "data": {}
            }
        }
    }

def unified_response(
    status_code: int, 
    message: Optional[str] = None, 
    data: Optional[Any] = None, 
    error: Optional[str] = None
) -> JSONResponse:
    """
    라우터 레이어에서 손쉽게 응답 규격을 생성하고 HTTP Status Code를 제어하기 위한 팩토리 함수
    """
    # 기본 응답 뼈대 빌드 (필요한 필드만 dynamic하게 조립)
    response_content = {"code": status_code}
    
    if message is not None:
        response_content["message"] = message
    if data is not None:
        response_content["data"] = data
    if error is not None:
        response_content["error"] = error
        
    return JSONResponse(
        status_code=status_code, 
        content=response_content
    )