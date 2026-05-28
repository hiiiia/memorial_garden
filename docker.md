## 초기 환경 구축 (최초 1회)
# 베이스 이미지 빌드 (이름을 python-base로 지정)
docker build -t python-base:latest -f docker-base/python-base.Dockerfile .

# 전체 서비스 실행
docker-compose up -d

## 컨테이너 내부 명령 실행 (쉘 접속) 패키지를 추가하거나 디버깅이 필요할 때 컨테이너 내부로 직접 들어갑니다.
# 백엔드 컨테이너 내부 쉘 접속
docker exec -it <컨테이너ID> /bin/bash

## 백엔드 서버 로그 확인 (매우 중요 ⭐️)
# DB 컨테이너가 잘 떴는지, 백엔드가 DB와 성공적으로 연결되었는지 실시간 로그를 확인합니다.
docker-compose logs -f backend


# 컨테이너 안에서 패키지 추가 설치
pip install requests

## 실시간 코드 수정 (Hot-Reload)
backend/app/main.py 파일을 수정하고 저장하면, 컨테이너 내 uvicorn이 자동으로 감지하여 서버를 재시작합니다.
웹 브라우저에서 localhost:8000을 새로고침하면 즉시 반영됩니다.