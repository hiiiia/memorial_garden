# 기억정원 Raspberry Pi 5 하드웨어 API

이 서비스는 Raspberry Pi OS 호스트에서 직접 실행되는 FastAPI 서버입니다. 기존 Docker 기반 `hardware/agent`, backend, frontend, ai 서비스와 독립적으로 동작하며 Docker Compose에는 포함되지 않습니다.

## 구성

```text
hardware/
├── README_hardware.md
└── host_service/
    ├── main.py              # FastAPI 엔드포인트와 CORS/서버 설정
    ├── audio_controller.py  # ALSA 탐색 및 arecord/aplay 프로세스 제어
    ├── requirements.txt
    ├── .env.example
    ├── recordings/          # 실행 시 자동 생성되는 녹음 폴더
    └── audio/               # 재생을 허용할 정적 WAV 폴더(선택)
```

`gpio_controller.py`는 이번 서비스에서 사용하지 않습니다. 물리 GPIO 버튼 대신 추후 React 화면이 이 HTTP API를 호출하도록 연결합니다.

## Raspberry Pi 준비

```bash
sudo apt update
sudo apt install -y alsa-utils python3-venv
sudo usermod -aG audio "$USER"
```

`audio` 그룹 추가 후에는 로그아웃/로그인이 필요할 수 있습니다.

```bash
cd ~/memorial_garden/hardware/host_service
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

## 실행

요구되는 기본 실행 명령은 다음과 같습니다.

```bash
cd ~/memorial_garden/hardware/host_service
uvicorn main:app --host 0.0.0.0 --port 8002
```

`.env`의 `HARDWARE_PORT`를 사용하려면 다음처럼 직접 실행할 수도 있습니다.

```bash
python3 main.py
```

오디오 장치 없이 실행 가능한 단위 테스트는 다음과 같습니다.

```bash
python3 -m unittest discover -s tests -v
```

## API 사용 예시

상태와 자동 탐지된 ALSA 장치를 확인합니다.

```bash
curl http://127.0.0.1:8002/health
curl http://127.0.0.1:8002/hardware/status
```

녹음을 시작하고 중지합니다.

```bash
curl -X POST http://127.0.0.1:8002/hardware/record/start
curl -X POST http://127.0.0.1:8002/hardware/record/stop
```

녹음은 `mono / 48000Hz / S32_LE / WAV` 형식이며 파일명은 `recording_YYYYMMDD_HHMMSS_uuid.wav` 형식입니다. 중지 API는 WAV 헤더와 포맷을 검증한 뒤 파일 경로, 크기, 오디오 길이를 반환합니다.

최근 녹음 목록을 확인합니다.

```bash
curl "http://127.0.0.1:8002/hardware/recordings?limit=20"
```

저장된 WAV를 비동기로 재생하고 중지합니다. `path`에는 `recordings/` 또는 `host_service/audio/` 안의 파일만 지정할 수 있습니다.

```bash
curl -X POST http://127.0.0.1:8002/hardware/audio/play \
  -H 'Content-Type: application/json' \
  -d '{"path":"/home/pi/memorial_garden/hardware/host_service/recordings/recording_20260624_120000_example.wav"}'

curl -X POST http://127.0.0.1:8002/hardware/audio/stop
```

재생 중 새 재생 요청이 오면 기존 `aplay` 프로세스를 안전하게 중지한 뒤 새 파일로 교체합니다. 녹음과 재생은 동시에 실행되지 않으며 충돌 요청에는 HTTP 409를 반환합니다.

## ALSA 장치 확인과 자동 탐색

Raspberry Pi에서 다음 명령으로 장치 목록을 확인할 수 있습니다.

```bash
arecord -l
aplay -l
cat /proc/asound/cards
```

서비스는 기본적으로 `/proc/asound/cards`, `arecord -l`, `aplay -l` 순서로 `Google voiceHAT Soundcard` 또는 정규화된 `googlevoicehat` 문자열을 찾습니다. 탐지된 카드 번호가 2라면 내부 장치명은 `plughw:2,0`이 되지만, 코드에는 카드 번호를 고정하지 않습니다. HDMI/DSI 디스플레이 연결로 카드 번호가 바뀌어도 API 요청 시 다시 탐색합니다.

탐지 키워드를 바꾸려면 `.env`를 수정합니다.

```dotenv
AUDIO_CARD_MATCH=googlevoicehat
```

자동 탐지가 실패한 경우에만 장치를 직접 지정합니다. 아래 카드 번호는 예시이며 현재 장치 목록에 맞춰야 합니다.

```dotenv
AUDIO_CAPTURE_DEVICE=plughw:2,0
AUDIO_PLAYBACK_DEVICE=plughw:2,0
```

장치를 찾지 못해도 서버와 `/health`는 실행됩니다. 이때 health 상태는 `degraded`이며 녹음/재생 API는 탐지 실패 원인을 포함한 HTTP 503을 반환합니다.

기존 터미널 테스트와 동일한 수동 점검 예시는 다음과 같습니다.

```bash
arecord -D plughw:2,0 -c 1 -r 48000 -f S32_LE -t wav test.wav
aplay -D plughw:2,0 test.wav
```

## 환경변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `AUDIO_CARD_MATCH` | `Google voiceHAT Soundcard` | ALSA 카드 검색 문자열 |
| `AUDIO_CAPTURE_DEVICE` | 비어 있음 | 캡처 장치 강제 지정 |
| `AUDIO_PLAYBACK_DEVICE` | 비어 있음 | 재생 장치 강제 지정 |
| `AUDIO_RECORDINGS_DIR` | `host_service/recordings` | 녹음 저장 폴더 |
| `HARDWARE_PORT` | `8002` | `python3 main.py` 실행 포트 |
| `HARDWARE_CORS_ORIGINS` | localhost 개발 origin 목록 | 쉼표로 구분한 허용 origin |
| `HARDWARE_LOG_LEVEL` | `INFO` | Python 로그 레벨 |

다른 PC에서 Raspberry Pi API를 호출한다면 React가 제공되는 정확한 origin을 `HARDWARE_CORS_ORIGINS`에 추가합니다.

## 확장 지점

- 녹음 완료 후 `AudioController._notify_recording_completed()`가 호출됩니다. 백엔드 업로드 API 명세가 확정되면 `recording_completed_hook`에 업로드 함수를 주입할 수 있습니다.
- `GET /hardware/recordings`에는 보존 기간 또는 최대 용량 기반 정리 정책을 연결할 TODO가 있습니다. 현재는 오래된 파일을 자동 삭제하지 않습니다.
