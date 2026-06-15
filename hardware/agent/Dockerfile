# 라즈베리 파이 5(Bookworm) 환경에 맞춘 Python 3.10 슬림 이미지 사용
FROM python:3.10-slim-bookworm

WORKDIR /app

# 파이썬 환경 변수 설정 (버퍼링 방지 및 바이트코드 생성 방지)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 시스템 패키지 설치: PyAudio, STT 및 GPIO 제어를 위한 필수 C 라이브러리 추가
RUN apt-get update && apt-get install -y \
    alsa-utils \
    libasound2-dev \
    portaudio19-dev \
    flac \
    gcc \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 파이썬 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사 (모듈화된 src 폴더 전체를 복사)
COPY ./src ./src

# 로컬 웹소켓 포트(8765) 노출
EXPOSE 8765

# 에이전트 통합 실행 파일 구동 (audio, ws, gpio를 모두 묶어서 실행)
CMD ["python", "src/main.py"]