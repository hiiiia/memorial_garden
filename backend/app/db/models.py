import uuid
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base

# ID 자동 생성기 (UUID4를 32자리 문자열로 변환)
def generate_uuid():
    return uuid.uuid4().hex

class Guardian(Base):
    __tablename__ = "guardians"

    # default=generate_uuid 추가
    id = Column(String(50), primary_key=True, index=True, default=generate_uuid)
    username = Column(String(50), unique=True, index=True)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(50), nullable=False)
    phone = Column(String(20), nullable=False)
    
    # 카카오 유저 고유 식별자 컬럼 추가 (일반 가입 유저를 위해 nullable=True)
    kakao_id = Column(String(50), unique=True, index=True, nullable=True)
    
    # 카카오 메시지 전송을 위한 토큰 저장 컬럼
    kakao_access_token = Column(String(255), nullable=True)
    kakao_refresh_token = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())

    dependents = relationship("Dependent", back_populates="guardian")

class Dependent(Base):
    __tablename__ = "dependents"

    id = Column(String(50), primary_key=True, index=True, default=generate_uuid)
    guardian_id = Column(String(50), ForeignKey("guardians.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(50), nullable=False)
    age = Column(Integer, nullable=False)
    device_token = Column(String(100), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    guardian = relationship("Guardian", back_populates="dependents")
    logs = relationship("Log", back_populates="dependent")
    alerts = relationship("Alert", back_populates="dependent")

class Log(Base):
    __tablename__ = "logs"

    id = Column(String(50), primary_key=True, index=True, default=generate_uuid)
    dependent_id = Column(String(50), ForeignKey("dependents.id", ondelete="CASCADE"), nullable=False)
    file_url = Column(String(255), nullable=False)
    status = Column(String(20), default="PROCESSING", nullable=False)
    
    # String(1000) -> Text 로 변경 (길이 제한 해제)
    stt_text = Column(Text, nullable=True)      
    reply_text = Column(Text, nullable=True)   
    reply_audio_url = Column(String(500), nullable=True) # TTS 연동 시 사용
    risk_score = Column(Float, default=0.0, nullable=False)
    primary_emotion = Column(String(20), nullable=True)    
    # LLM 요약도 혹시 길어질 수 있으니 Text로 넉넉하게 잡습니다.
    llm_summary = Column(Text, nullable=True)       
    
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