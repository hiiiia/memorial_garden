FROM python-base:latest

WORKDIR /app

# requirements.txt 복사 및 설치 (캐싱 활용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드는 docker-compose의 volumes를 통해 마운트되므로 
# 별도로 COPY ./app ./app 를 하지 않아도 개발 모드에서 동작합니다.

EXPOSE 8000

# --reload 옵션을 추가하여 코드 수정 시 자동 재시작
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]








### docker-compose down   
### docker-compose up --build -d
### docker-compose logs -f backend
### docker-compose restart backend