# 🏡 Memorial Garden - Edge Agent (Raspberry Pi)

이 디렉토리는 Memorial Garden 시스템의 최전선에서 사용자의 음성을 수집하고 전처리하는 **라즈베리 파이 기반 Edge Agent**의 소스 코드를 포함합니다.

본 에이전트는 어르신의 음성을 수집하지만, **Zero-PII(개인정보 무저장) 정책**에 따라 민감한 발화 원문(`stt_text`)이나 과거 기억 데이터는 외부 서버로 전송하지 않고 온디바이스 로컬 DB에만 격리하여 저장합니다.



---

## 🔄 핵심 라우팅 흐름 (Data Routing & Pipeline)

Edge Agent는 단순한 녹음기가 아닙니다. 수집된 음성을 분석하고, 로컬 기억을 덧붙여 AI 서버로 안전하게 라우팅하는 지능형 파이프라인을 갖추고 있습니다.

```text
[1. 🎤 음성 입력] : React 사용자 화면(`/elder`)의 웹소켓 명령(`{"command":"force_record"}`)으로 녹음 시작/종료.
       ⬇️
[2. 📝 STT & RAG] : 녹음된 음성(.wav)을 텍스트로 변환 후, 로컬 Vector DB를 검색하여 관련된 과거 기억(Context) 추출.
       ⬇️
[3. 🧠 UI 라우팅] : 추출된 기억을 바탕으로 즉각적인 AI 응답(텍스트/추임새)을 프론트엔드로 전달하여 대화 흐름 유지.
       ⬇️
[4. 🚀 비동기 큐] : 무거운 음향 분석을 위해 (오디오 파일 + 텍스트 + 유저ID)를 백그라운드 `audio_task_queue`에 삽입. (UI 블로킹 해제)
       ⬇️
[5. 🌐 서버 전송] : 백그라운드 워커가 큐에서 작업을 꺼내 AI Orchestrator 서버로 안전하게 업로드.
       ⬇️
[6. 🗑️ 보안 파기] : AI 서버 전송이 완료된 즉시 엣지 디바이스 내의 원본 오디오 파일(.wav) 영구 삭제 (Zero-PII).
```

## ✨ 핵심 기능 (Key Features)

1. **Zero-PII 온디바이스 데이터 격리**
   - 발화 텍스트와 추출된 기억 정보는 라즈베리 파이 내부의 `local_memory_db`에만 저장됩니다.
   - 중앙 AI 서버로는 정량화된 데이터(분석용 오디오, 통계 메타데이터)만 익명화되어 전송됩니다.
2. **비동기 토글(Start/Stop) 녹음 파이프라인**
   - React 웹소켓 명령(`force_record`)에 반응하여 Pi 호스트 모드에서는 `hardware.host_service.audio_controller.AudioController` 기반 녹음을 수행합니다.
   - Docker agent 모드에서는 실제 I2S 장치를 점유하지 않으며, 오디오 제어는 Raspberry Pi OS 호스트 실행 모드에서 담당합니다.
3. **Task Queue 기반 백그라운드 워커**
   - 무거운 STT 추론, 로컬 RAG 검색, AI 서버로의 파일 업로드 로직을 `audio_task_queue` 워커로 분리하여 프론트엔드 UI의 무한 로딩(Blocking)을 방지합니다.
4. **하드웨어 제약 없는 TEST_MODE 지원**
   - 실제 마이크 하드웨어가 연결되어 있지 않아도, 로컬 오디오 파일(`test_1.mp3`)을 활용해 전체 시스템 파이프라인(Edge -> AI -> Backend)을 검증할 수 있습니다.

---

## 📁 디렉토리 구조 (Directory Structure)

```text
hardware/
├── Dockerfile              # Docker agent 개발/운영 이미지
├── docker-compose.yml
├── host_service/           # 공용 AudioController 및 FastAPI 진단 REST 래퍼
├── requirements.txt        # WebSocket/AI/로컬 DB agent 의존성
├── local_memory_db/        # [격리 공간] 로컬 Vector DB 저장소
└── src/
    ├── main.py             # 메인 웹소켓 서버 및 비동기 워커 실행
    ├── audio_controller.py # 레거시 모듈(신규 실제 I2S 제어는 host_service/audio_controller.py 사용)
    ├── gpio_controller.py  # 하드웨어 핀/버튼 제어 로직 (해당 시)
    ├── database.py         # 로컬 RAG용 온디바이스 DB 접근 로직
    ├── config.py           # 환경 변수 및 설정 (서버 URL 등)
    └── test_1.mp3          # [테스트용] 더미 오디오 파일

```

🚀 설치 및 실행 방법 (Getting Started)
기존 Docker 실행은 유지되지만, 실제 I2S 마이크·스피커 제어는 Raspberry Pi OS 호스트 실행 모드에서만 수행합니다.

1. 사전 요구 사항 (Prerequisites)
Docker 및 Docker Compose 설치

(실제 배포 시) USB 마이크 또는 I2S 마이크 연결

```bash
# 디렉토리 이동
cd memorial_garden/hardware

# 컨테이너 백그라운드 실행 (오디오 시스템 권한 자동 매핑)
docker-compose up --build -d

# 실행 로그 확인
docker logs -f aicare_agent
```

🧪 테스트 모드 (TEST_MODE) 가이드
마이크 하드웨어 세팅 없이 로컬 PC나 개발 환경에서 데이터 흐름을 테스트할 때 사용합니다.

1. 환경변수로 테스트 모드를 켭니다.

```bash
export TEST_MODE=true
export TEST_INPUT_TEXT="오늘 산책을 다녀왔어."
```

Pi 호스트에서 실제 오디오를 제어하려면 다음처럼 실행합니다.

```bash
cd ~/memorial_garden
export HARDWARE_RUNTIME_MODE=host
python3 -m hardware.agent.main
```

FastAPI 진단 서버는 agent와 동시에 실행하지 말고, 단독으로 다음 명령을 사용합니다.

```bash
cd ~/memorial_garden
uvicorn hardware.host_service.main:app --host 0.0.0.0 --port 8002
```
2. 테스트용 오디오 파일인 test_1.mp3를 반드시 src/ 디렉토리 안에 위치시킵니다.

3. React 프론트엔드에서 '말하기' 버튼을 클릭하여 테스트를 진행합니다.

4. 
- [1차 클릭] 녹음 시작 시뮬레이션
- [2차 클릭] 녹음 정지 시뮬레이션 ➡️ test_1.mp3 복사 (audio_xxxx.wav 생성) ➡️ 백그라운드 워커가 AI 서버로 자동 전송

⚠️ WARNING: 상용 배포 전 반드시 TEST_MODE = False로 원복해 주세요!

