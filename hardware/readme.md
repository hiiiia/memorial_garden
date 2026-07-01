# Memorial Garden Hardware Agent

Raspberry Pi 5에서 실행되는 기억정원 하드웨어 에이전트입니다. React 사용자 화면의 WebSocket 명령(`force_record`)으로 I2S 녹음을 시작/종료하고, 녹음된 WAV를 로컬 STT로 텍스트화한 뒤 기존 `edge/route`와 `analyze/audio` 흐름에 연결합니다.

## 현재 STT 엔진

현재 `#19.2-stt-sherpa` 브랜치의 로컬 STT는 Sherpa-ONNX Korean Zipformer int8 오프라인 모델을 사용합니다.

```text
React force_record
→ I2S arecord WAV 저장
→ stt_task_queue
→ Sherpa-ONNX Korean Zipformer int8
→ 실제 stt_text
→ /api/v1/edge/route
→ audio_task_queue
→ /api/v1/analyze/audio
```

다른 STT 엔진 fallback은 두지 않습니다.

## 실행 구조

주요 파일:

```text
hardware/agent/src/main.py          # WebSocket 8765, force_record, queue, backend/AI 연동
hardware/agent/src/i2s_audio.py     # Google voiceHAT ALSA 자동 탐색, arecord/aplay 제어
hardware/agent/src/stt_sherpa.py    # Sherpa-ONNX 오프라인 STT 실행
hardware/sherpa_stt.py              # 저장소 루트에서 단독 STT 테스트용 wrapper
hardware/README_SHERPA_STT.md       # 모델 설치 및 테스트 절차
```

## Raspberry Pi 호스트 직접 실행

```bash
cd ~/memorial_garden/hardware/agent
PYTHONPATH=src python3 src/main.py
```

## 단독 STT 테스트

저장소 루트에서:

```bash
python3 -m hardware.sherpa_stt --file /path/to/test.wav
```

agent 폴더 기준:

```bash
cd ~/memorial_garden/hardware/agent
PYTHONPATH=src python3 -m stt_sherpa --file /path/to/test.wav
```

모델 다운로드, 환경변수, 성능 측정, 문제 해결은 [README_SHERPA_STT.md](README_SHERPA_STT.md)를 확인하세요.
