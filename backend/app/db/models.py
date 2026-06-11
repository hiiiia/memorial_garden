import uuid
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from .database import Base

# ID 자동 생성기 (UUID4를 32자리 문자열로 변환)
def generate_uuid():
    return uuid.uuid4().hex

class Guardian(Base):
    __tablename__ = "guardians"

    id = Column(String(50), primary_key=True, index=True, default=generate_uuid)
    username = Column(String(50), unique=True, index=True) # 새로 추가하신 컬럼
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(50), nullable=False)
    phone = Column(String(20), nullable=False)
    
    # 카카오 유저 고유 식별자 및 토큰 (새로 추가하신 컬럼)
    kakao_id = Column(String(50), unique=True, index=True, nullable=True)
    kakao_access_token = Column(String(255), nullable=True)
    kakao_refresh_token = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())

    # 1:N 직접 연결 대신, 매핑 테이블을 통한 연결
    dependent_links = relationship("GuardianDependentMapping", back_populates="guardian", cascade="all, delete-orphan")

class Dependent(Base):
    __tablename__ = "dependents"

    id = Column(String(50), primary_key=True, index=True, default=generate_uuid)
    
    # 어르신 독자적 앱 사용 및 검색을 위한 컬럼 유지
    username = Column(String(50), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=True)
    is_searchable = Column(Boolean, default=True) 
    
    name = Column(String(50), nullable=False)
    age = Column(Integer, nullable=False)
    device_token = Column(String(100), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    # 매핑 테이블 및 기존 관계 설정
    guardian_links = relationship("GuardianDependentMapping", back_populates="dependent", cascade="all, delete-orphan")
    logs = relationship("Log", back_populates="dependent")
    alerts = relationship("Alert", back_populates="dependent")

# 연동 수락/대기 상태를 관리하는 매핑 테이블
class GuardianDependentMapping(Base):
    __tablename__ = "guardian_dependent_mappings"

    id = Column(String(50), primary_key=True, index=True, default=generate_uuid)
    guardian_id = Column(String(50), ForeignKey("guardians.id", ondelete="CASCADE"), nullable=False)
    dependent_id = Column(String(50), ForeignKey("dependents.id", ondelete="CASCADE"), nullable=False)
    
    status = Column(String(20), default="PENDING", nullable=False) # PENDING, CONNECTED, REJECTED
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    guardian = relationship("Guardian", back_populates="dependent_links")
    dependent = relationship("Dependent", back_populates="guardian_links")

class Log(Base):
    __tablename__ = "logs"

    id = Column(String(50), primary_key=True, index=True, default=generate_uuid)
    dependent_id = Column(String(50), ForeignKey("dependents.id", ondelete="CASCADE"), nullable=False)
    file_url = Column(String(255), nullable=False)
    
    # 생성된 AI 그림일기 이미지 URL 저장용
    image_url = Column(String(500), nullable=True)
    status = Column(String(20), default="PROCESSING", nullable=False)
    
    # text 타입 적용 완료
    stt_text = Column(Text, nullable=True)      
    reply_text = Column(Text, nullable=True)   
    reply_audio_url = Column(String(500), nullable=True) 
    
    # 건강 지표 세분화 점수
    risk_score = Column(Float, default=0.0, nullable=False)
    depression_score = Column(Float, default=0.0, nullable=False)        # 추가!
    cognitive_decline_score = Column(Float, default=0.0, nullable=False) # 추가!
    
    primary_emotion = Column(String(20), nullable=True)    
    llm_summary = Column(Text, nullable=True)       
    
    # 프론트엔드 달력 UI용 텍스트 및 해시태그
    diary_text = Column(Text, nullable=True) # 추가! (동화풍 그림일기 본문)
    keywords = Column(Text, nullable=True)   # 추가! (해시태그 - 콤마로 구분하여 저장)
    
    # 어르신 장기 기억(RAG)용 벡터 컬럼
    # 구글 gemini-embedding-2 모델의 출력 차원인 3072에 맞춤
    vector_embedding = Column(Vector(3072), nullable=True)
    
    created_at = Column(DateTime, server_default=func.now(), index=True)

    dependent = relationship("Dependent", back_populates="logs")
    alerts = relationship("Alert", back_populates="log")
    
class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String(50), primary_key=True, index=True, default=generate_uuid)
    dependent_id = Column(String(50), ForeignKey("dependents.id", ondelete="CASCADE"), nullable=False)
    log_id = Column(String(50), ForeignKey("logs.id", ondelete="SET NULL"), nullable=True)
    
    trigger_type = Column(String(20), nullable=False)
    status = Column(String(20), default="PENDING", nullable=False)
    
    created_at = Column(DateTime, server_default=func.now(), index=True)

    dependent = relationship("Dependent", back_populates="alerts")
    log = relationship("Log", back_populates="alerts")