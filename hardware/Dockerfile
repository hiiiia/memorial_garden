# 라즈베리파이 아키텍처와 호환되는 베이스 이미지 (Python 3.7)
FROM python:3.7-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# ALSA 오디오 라이브러리 등 하드웨어 제어에 필요한 OS 패키지 설치
RUN apt-get update && apt-get install -y \
    alsa-utils \
    libasound2-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY ./src ./src

# 하드웨어 제어 메인 루프 실행
CMD ["python", "src/audio_controller.py"]
