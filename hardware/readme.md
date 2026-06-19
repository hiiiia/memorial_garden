# 🏡 Memorial Garden - Edge Agent (Raspberry Pi)

이 디렉토리는 Memorial Garden 시스템의 최전선에서 사용자의 음성을 수집하고 전처리하는 **라즈베리 파이 기반 Edge Agent**의 소스 코드를 포함합니다.

본 에이전트는 어르신의 음성을 수집하지만, **Zero-PII(개인정보 무저장) 정책**에 따라 민감한 발화 원문(`stt_text`)이나 과거 기억 데이터는 외부 서버로 전송하지 않고 온디바이스 로컬 DB에만 격리하여 저장합니다.



---

## 🔄 핵심 라우팅 흐름 (Data Routing & Pipeline)

Edge Agent는 단순한 녹음기가 아닙니다. 수집된 음성을 분석하고, 로컬 기억을 덧붙여 AI 서버로 안전하게 라우팅하는 지능형 파이프라인을 갖추고 있습니다.

```text
[1. 🎤 음성 입력] : React 프론트엔드의 웹소켓 명령(force_record)으로 스트리밍 녹음 시작/종료.
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
   - React 웹소켓 명령(`force_record`)에 반응하여 `sounddevice.InputStream` 기반의 비차단(Non-blocking) 녹음을 수행합니다.
3. **Task Queue 기반 백그라운드 워커**
   - 무거운 STT 추론, 로컬 RAG 검색, AI 서버로의 파일 업로드 로직을 `audio_task_queue` 워커로 분리하여 프론트엔드 UI의 무한 로딩(Blocking)을 방지합니다.
4. **하드웨어 제약 없는 TEST_MODE 지원**
   - 실제 마이크 하드웨어가 연결되어 있지 않아도, 로컬 오디오 파일(`test_1.mp3`)을 활용해 전체 시스템 파이프라인(Edge -> AI -> Backend)을 검증할 수 있습니다.

---

## 📁 디렉토리 구조 (Directory Structure)

```text
hardware/
├── Dockerfile              # 시스템 오디오 의존성(libportaudio2) 포함
├── docker-compose.yml
├── requirements.txt        # sounddevice, numpy, soundfile 등
├── local_memory_db/        # [격리 공간] 로컬 Vector DB 저장소
└── src/
    ├── main.py             # 메인 웹소켓 서버 및 비동기 워커 실행
    ├── audio_controller.py # 오디오 스트리밍 녹음 및 파일 저장 제어
    ├── gpio_controller.py  # 하드웨어 핀/버튼 제어 로직 (해당 시)
    ├── database.py         # 로컬 RAG용 온디바이스 DB 접근 로직
    ├── config.py           # 환경 변수 및 설정 (서버 URL 등)
    └── test_1.mp3          # [테스트용] 더미 오디오 파일

```

🚀 설치 및 실행 방법 (Getting Started)
본 프로젝트는 Docker 환경에 최적화되어 있습니다. 컨테이너 내부 절대 경로(/app/src/)를 사용하므로 호스트 OS의 환경에 구애받지 않습니다.

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

1. src/main.py 파일 내 상단 설정을 변경합니다.

```Python
TEST_MODE = True
```
2. 테스트용 오디오 파일인 test_1.mp3를 반드시 src/ 디렉토리 안에 위치시킵니다.

3. React 프론트엔드에서 '말하기' 버튼을 클릭하여 테스트를 진행합니다.

4. 
- [1차 클릭] 녹음 시작 시뮬레이션
- [2차 클릭] 녹음 정지 시뮬레이션 ➡️ test_1.mp3 복사 (audio_xxxx.wav 생성) ➡️ 백그라운드 워커가 AI 서버로 자동 전송

⚠️ WARNING: 상용 배포 전 반드시 TEST_MODE = False로 원복해 주세요!

