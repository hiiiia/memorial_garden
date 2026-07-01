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

---

## Raspberry Pi 5 로컬 STT: whisper.cpp

현재 하드웨어 에이전트는 React 화면의 `force_record` 명령으로 I2S 녹음을 시작/종료하고, 녹음된 WAV를 Raspberry Pi 5 로컬의 `whisper.cpp`로 STT 처리합니다. STT는 별도 worker queue에서 1건씩 처리되어 Chromium UI와 버튼 처리 흐름을 막지 않도록 구성되어 있습니다.

### 1. whisper.cpp 빌드

```bash
cd /home/pi
git clone https://github.com/ggerganov/whisper.cpp.git
cd whisper.cpp
cmake -B build
cmake --build build -j2
```

빌드 후 실행 파일 예시는 다음 경로입니다.

```bash
/home/pi/whisper.cpp/build/bin/whisper-cli
```

### 2. 한국어 지원 모델 다운로드

`base.en`은 영어 전용이므로 사용하지 마세요. 한국어에는 다국어 `ggml-base.bin`을 사용합니다.

```bash
cd /home/pi/whisper.cpp
bash ./models/download-ggml-model.sh base
ls -lh /home/pi/whisper.cpp/models/ggml-base.bin
```

### 3. 환경 변수 설정

`hardware/.env`에 아래 값을 설정합니다. 실제 경로가 다르면 Pi의 설치 위치에 맞게 변경하세요.

```env
WHISPER_CPP_BIN=/home/pi/whisper.cpp/build/bin/whisper-cli
WHISPER_MODEL_PATH=/home/pi/whisper.cpp/models/ggml-base.bin
WHISPER_LANGUAGE=ko
WHISPER_THREADS=3
WHISPER_NICE=10
WHISPER_TIMEOUT_SECONDS=180
```

UI가 버벅이면 먼저 스레드를 줄입니다.

```env
WHISPER_THREADS=2
```

### 4. 테스트 WAV 실행

저장소 루트에서:

```bash
python3 -m hardware.stt_whisper --file /path/to/test.wav
```

Docker/agent src 경로만 사용하는 환경에서는:

```bash
cd hardware/agent
PYTHONPATH=src python3 -m stt_whisper --file /path/to/test.wav
```

출력에는 WAV 경로, 파일 크기, 시작/종료 시각, 처리 시간, 인식 텍스트 또는 오류 원인이 표시됩니다.

### 5. 실제 에이전트 실행

현재 Docker 구조를 변경하지 않습니다. 기존 실행 방식 그대로 agent를 시작합니다.

```bash
cd memorial_garden/hardware
docker compose up -d --build agent
docker logs -f aicare_agent
```

주의: Docker 안에서 실행할 경우 `WHISPER_CPP_BIN`과 `WHISPER_MODEL_PATH`는 컨테이너 내부에서 접근 가능한 경로여야 합니다. 이번 작업에서는 Docker Compose mount 구조를 변경하지 않았으므로, `/home/pi/whisper.cpp`가 컨테이너에 보이지 않는 환경에서는 호스트 직접 실행 방식으로 먼저 검증하세요.

호스트에서 직접 실행하는 경우:

```bash
cd memorial_garden/hardware/agent
PYTHONPATH=src python3 src/main.py
```

### 6. 문제 해결

- `whisper-cli` 파일 없음: `WHISPER_CPP_BIN` 경로와 빌드 결과를 확인하세요.
- 모델 파일 없음: `/home/pi/whisper.cpp/models/ggml-base.bin`이 있는지 확인하세요.
- 권한 문제: `chmod +x /home/pi/whisper.cpp/build/bin/whisper-cli`를 확인하세요.
- WAV 포맷 문제: 현재 I2S 녹음은 mono 48kHz S32_LE일 수 있습니다. whisper.cpp는 16kHz mono 16-bit PCM을 권장하므로 로그에 경고가 표시될 수 있습니다. 변환이 필요하면 `ffmpeg` 설치 여부를 먼저 확인하고 별도 변환 단계로 분리하세요.
- 처리 시간이 너무 길 때: `WHISPER_THREADS=2`로 낮추고, Chromium 탭 수와 백그라운드 프로세스를 줄이세요.
- UI가 버벅일 때: 기본 명령은 `nice -n 10`으로 실행되어 UI 우선순위를 높입니다. 그래도 느리면 `WHISPER_THREADS=2`를 사용하세요.

