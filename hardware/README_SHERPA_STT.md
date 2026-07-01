# Raspberry Pi 5 Sherpa-ONNX Korean STT

이 문서는 Raspberry Pi 5에서 기억정원 하드웨어 에이전트의 로컬 STT를 Sherpa-ONNX Korean Zipformer int8 오프라인 모델로 실행하는 절차입니다.

## 1. Python 가상환경 준비

```bash
cd ~/memorial_garden/hardware/agent
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

`requirements.txt`에는 Raspberry Pi OS 64-bit / ARM64 wheel이 제공되는 `sherpa-onnx==1.13.2`를 사용합니다.

## 2. Sherpa 모델 다운로드

모델은 런타임에 자동 다운로드하지 않습니다. 직접 내려받아 repository 내부의 기본 경로에 압축을 해제합니다.

```bash
cd ~/memorial_garden/hardware
mkdir -p models
cd models
wget https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-zipformer-korean-2024-06-24.tar.bz2
tar xf sherpa-onnx-zipformer-korean-2024-06-24.tar.bz2
rm sherpa-onnx-zipformer-korean-2024-06-24.tar.bz2
```

최종 경로:

```text
~/memorial_garden/hardware/models/sherpa-onnx-zipformer-korean-2024-06-24/
```

현재 코드는 모델 디렉터리에서 다음 파일을 사용합니다.

```text
encoder-epoch-99-avg-1.int8.onnx
decoder-epoch-99-avg-1.int8.onnx
joiner-epoch-99-avg-1.int8.onnx
tokens.txt
```

확인 명령:

```bash
ls -lh ~/memorial_garden/hardware/models/sherpa-onnx-zipformer-korean-2024-06-24
```

## 3. 환경변수

`hardware/.env` 또는 실행 쉘에 설정합니다.

```env
SHERPA_MODEL_DIR=/home/pi/memorial_garden/hardware/models/sherpa-onnx-zipformer-korean-2024-06-24
SHERPA_NUM_THREADS=4
```

`SHERPA_MODEL_DIR`를 생략하면 저장소 내부 기본 경로 `hardware/models/sherpa-onnx-zipformer-korean-2024-06-24/`를 사용합니다.

`SHERPA_NUM_THREADS` 기본값은 `min(4, CPU 코어 수)`입니다. UI가 버벅이면 다음처럼 줄입니다.

```env
SHERPA_NUM_THREADS=2
```

## 4. WAV 형식

Sherpa 입력은 mono, 16-bit PCM WAV여야 합니다. 현재 I2S 녹음 명령은 STT 변환 비용을 줄이기 위해 녹음 단계에서 다음 형식으로 저장합니다.

```text
arecord -D plughw:<자동탐색카드>,0 -c 1 -r 16000 -f S16_LE -t wav <파일>
```

Raspberry Pi에서 `plughw`가 INMP441 입력을 16kHz/S16_LE로 변환하지 못하면 녹음 단계에서 오류가 날 수 있습니다. 이 경우 실제 ALSA 지원 형식을 확인한 뒤 별도 변환 단계를 추가해야 합니다.

## 5. 단독 STT 테스트

저장소 루트에서:

```bash
cd ~/memorial_garden
python3 -m hardware.sherpa_stt --file /path/to/5sec_test.wav
```

agent 폴더에서:

```bash
cd ~/memorial_garden/hardware/agent
PYTHONPATH=src python3 -m stt_sherpa --file /path/to/5sec_test.wav
```

출력에서 다음을 확인합니다.

```text
[STT] engine=sherpa-onnx-korean-zipformer-int8
[STT] audio=5.02s, sample_rate=16000, channels=1, width=16bit
[STT] model=loaded 또는 reused
[STT] inference=0.42s, rtf=0.084
[STT] text=오늘은 손주와 공원에 다녀왔어요
```

## 6. 에이전트 실행

Raspberry Pi 호스트 직접 실행:

```bash
cd ~/memorial_garden/hardware/agent
source .venv/bin/activate
PYTHONPATH=src python3 src/main.py
```

Docker 실행은 기존 구조를 바꾸지 않았습니다. Docker 내부에서 Sherpa 모델 디렉터리가 보이지 않으면 `SHERPA_MODEL_DIR`와 volume mount를 Pi 테스트 환경에서 별도로 맞춰야 합니다.

## 7. Whisper 3.1초와 비교 측정

동일 WAV 파일로 다음 값을 비교합니다.

```text
inference seconds
RTF = inference seconds / audio seconds
```

예:

```bash
PYTHONPATH=src python3 -m stt_sherpa --file /path/to/same_5sec.wav
```

로그의 `inference=` 값이 기존 Whisper 처리 시간 3.1초보다 낮은지 확인합니다.

## 8. 문제 해결

- `MISSING_SHERPA_ONNX`: `python3 -m pip install -r hardware/agent/requirements.txt`를 다시 실행합니다.
- `MISSING_MODEL_DIR`: `SHERPA_MODEL_DIR` 경로와 모델 다운로드 위치를 확인합니다.
- `MISSING_MODEL_FILE`: 모델 압축이 올바르게 풀렸는지, int8 ONNX 파일과 `tokens.txt`가 있는지 확인합니다.
- `UNSUPPORTED_SAMPLE_WIDTH`: WAV가 16-bit PCM이 아닙니다. 현재 녹음 설정이 `S16_LE`인지 확인합니다.
- `UNSUPPORTED_CHANNELS`: WAV가 mono가 아닙니다. `arecord -c 1` 설정을 확인합니다.
- 녹음 실패: `arecord -l`, `aplay -l`, `cat /proc/asound/cards`로 `Google voiceHAT Soundcard` 탐지 여부를 확인합니다.
- UI가 느림: `SHERPA_NUM_THREADS=2`로 낮춥니다.
