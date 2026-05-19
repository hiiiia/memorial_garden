# 공통 Python 3.7 슬림 이미지
FROM python:3.7-slim

# 개발에 필요한 최소 도구 및 하드웨어 라이브러리 미리 설치
RUN apt-get update && apt-get install -y \
    gcc \
    git \
    curl \
    libasound2-dev \
    alsa-utils \
    && rm -rf /var/lib/apt/lists/*

# 파이프 업그레이드 및 공통 패키지 설치
RUN pip install --no-cache-dir --upgrade pip
