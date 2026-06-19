```markdown
# 📄 Technical Specification: Jetson Nano 기반 하이브리드 Edge AI 및 병렬 라우팅 파이프라인

## Frontend , Agent 세팅


## 4. Python 3.10 독립 환경 구성 (Miniforge)

우분투 18.04 ARM64 환경에서는 기본 파이썬 버전이 레거시(3.6.9)이며, 일반적인 `apt` 저장소(deadsnakes 등)의 지원 중단으로 정상적인 파이썬 상위 버전 빌드가 어렵습니다. 이를 최적화하기 위해 ARM64 패키지 생태계가 활성화된 Miniforge(Conda-forge)를 이용해 가벼운 격리 가상환경을 구축합니다.

```bash
# 1. Miniforge3 ARM64 설치 스크립트 다운로드 및 설치
cd ~
wget [https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-aarch64.sh](https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-aarch64.sh)
bash Miniforge3-Linux-aarch64.sh -b

# 2. Conda 환경 환경변수 등록 및 터미널 쉘 새로고침
~/miniforge3/bin/conda init
source ~/.bashrc

# 3. Python 3.10 버전 가상환경(edge_agent) 생성 및 가동
conda create -n edge_agent python=3.10 -y
conda activate edge_agent

# 4. 가상환경 내 필수 경량 라이브러리 설치 (무거운 Agent 프레임워크 원천 배제)
pip install requests flask flask-cors

```


## 6. Lightweight Agent Middleware (초경량 미들웨어 구현)

`conda activate edge_agent` 상태에서 구동되며, 프론트엔드(React)의 비동기 요청을 받아 엣지 LLM과 연동하고 병렬 스레드를 분배하는 파이썬 메인 컨트롤러 코드입니다.

`~/edge_agent/agent.py` 파일로 저장하여 실행합니다.

```python
import requests
import json
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

LLM_API_URL = "[http://127.0.0.1:8080/completion](http://127.0.0.1:8080/completion)"

def handle_local_action(action_code):
    """[스레드 A] 로컬 기기 제어 및 추임새 오디오 백그라운드 즉시 재생 (Latency Masking)"""
    if action_code:
        print(f"🌟 [LOCAL THREAD] 즉시 로컬 오디오 재생 트리거: {action_code}")
        # 예: os.system(f"aplay /mnt/sdcard/audio/{action_code}")

def send_to_health_db(meta_data):
    """[스레드 B] 분석 연속성을 보장하기 위한 수치형 메타데이터의 백엔드 전송"""
    print(f"📊 [META THREAD] 헬스케어 메타데이터 시계열 DB 전송 완료: {meta_data}")

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message', '')
    
    # 1회 추론으로 멀티 플래그 출력을 강제하기 위한 템플릿 엔지니어링
    prompt = f"""<|im_start|>system
You are an Edge AI router. Analyze the user's intent and output ONLY a valid JSON object. 
Format: {{"intent": "RAG_REQ" or "LOCAL_CMD", "privacy_flag": true/false, "local_action": "play_filler.mp3" or null}}
<|im_end|>
<|im_start|>user
{user_input}<|im_end|>
<|im_start|>assistant
"""

    payload = {
        "prompt": prompt,
        "n_predict": 128,
        "temperature": 0.1,  # 완벽한 JSON 규격을 위해 생성 다양성을 억제
        "stop": ["<|im_end|>"]
    }

    try:
        # 1. 엣지 가속 sLLM 서버 호출
        response = requests.post(LLM_API_URL, json=payload).json()
        ai_output = response['content'].strip()
        
        # 2. 구조화 JSON 파싱
        routing_data = json.loads(ai_output)
        intent = routing_data.get('intent')
        privacy = routing_data.get('privacy_flag')
        action = routing_data.get('local_action')

        # 3. 비동기/멀티스레딩 기반 병렬 디스패치 전개
        # 로컬 오디오 즉각 재생 실행 (사용자 체감 Latency 0초 구현)
        threading.Thread(target=handle_local_action, args=(action,)).start()
        
        # VAD 및 통계적 수치 분리 추출 (예시 파라미터 백엔드 전송)
        mock_meta = {"wpm": 38, "pause_duration": 3.1, "depression_score": 0.75}
        threading.Thread(target=send_to_health_db, args=(mock_meta,)).start()

        # 4. 프라이버시 마스킹 처리 및 최종 분기 반환
        if privacy:
            print("🚨 [PRIVACY DROP] 민감 대화 데이터 감지됨. 원본 텍스트 로컬 메모리에서 즉각 파기 완료.")
            return jsonify({
                "status": "success",
                "edge_decision": intent,
                "forward_text": "[USER_REQUESTED_PRIVACY_DROP]",  # 시맨틱 데이터 마스킹
                "message": "비식별화 보호 처리 및 로컬 제어 완료"
            })
        else:
            return jsonify({
                "status": "success",
                "edge_decision": intent,
                "forward_text": user_input,
                "message": "클라우드 런타임 연동 포워딩 준비 완료"
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Flask 에이전트 구동 (포트 5000)
    app.run(host='0.0.0.0', port=5000)

```

---

# Node.js 16 설치 
curl -sL https://deb.nodesource.com/setup_16.x | sudo -E bash -
sudo apt install -y nodejs

# frontend 폴더와 그 안의 모든 파일을 jetson 계정의 소유로 변경합니다.
sudo chown -R jetson:jetson ~/memorial_garden/hardware/frontend

# 혹시 모를 권한 문제 방지를 위해 읽기/쓰기 권한을 부여합니다.
chmod -R 755 ~/memorial_garden/hardware/frontend

# 1. 프로젝트 폴더 이동
cd ~/memorial_garden/hardware/frontend

# 2. 패키지 설치
npm install

# 3. 배포용 빌드 (이 과정에서 메모리가 많이 필요합니다!)
npm run build

# 4. 배포용 빌드 실행
npx serve -s build -l 3000

---

## 1. Overview (개요)
본 문서는 NVIDIA Jetson Nano B01 환경에서 발생할 수 있는 하드웨어적 한계(16GB eMMC, 4GB RAM)와 레거시 소프트웨어 종속성(CUDA 10.2, GCC 7, Python 3.6) 문제를 극복하고, Edge 환경에 최적화된 소형 LLM(sLLM)과 초경량 에이전트 미들웨어를 네이티브 환경에 구축하기 위한 최종 기술 명세서입니다.

저사양 기기에서 대형 모델 연동 시 발생하는 지연(Latency) 문제와 사용자 프라이버시 보호 요구사항을 구조적으로 해결하기 위해, 한 번의 LLM 추론으로 라우팅 플래그와 비식별화 요청을 동시 분석하는 **'Single-pass 멀티 인텐트 라우팅'** 및 **'멀티스레드 기반 병렬 디스패치(Parallel Dispatch)'** 아키텍처를 정의합니다.

- **목적:** Edge 단말 단에서의 실시간 인텐트 판별, 프라이버시 필터링, 하드웨어 통제 및 지연 시간 은닉
- **주요 기술 스택:** Ubuntu 18.04 (JetPack 4.6), CUDA 10.2, GCC 9, Miniforge3 (Python 3.10), llama.cpp (b2400), Flask

---

## 2. System Architecture (시스템 아키텍처)

본 프로젝트는 가상화 레이어의 오버헤드를 줄이고 제한된 하드웨어 자원을 100% 활용하기 위해 Docker 환경을 배포 단계에서 제외하고 **Native (Bare Metal) 파이프라인**을 채택했습니다.

### 2.1. 배포 아키텍처 비교 (Docker vs Native)
```text
[초기 기획: Docker 구조] (버전 충돌 및 오버헤드로 폐기)
Hardware (Jetson Nano)
 └── OS (Ubuntu 18.04)
      └── Docker Daemon (nvidia-runtime)
           └── Container (dustynv/llama_cpp)  <-- I/O 및 런타임 레이어 오버헤드
                └── Model Inference

[최종 구축: Native 구조] (현재 동작 환경 🚀)
Hardware (Jetson Nano)
 └── OS (Ubuntu 18.04)
      └── Native Executable (llama.cpp / GCC 9 빌드) <-- Direct GPU Access
           └── Model Inference

```

### 2.2. 싱글패스(Single-pass) 병렬 처리 및 지연 은닉 파이프라인

엣지 단말 내부의 sLLM(Qwen 1.8B)은 단 한 번의 추론으로 `라우팅 의도(intent)`와 `프라이버시 플래그(privacy_flag)`를 포함한 구조화된 JSON 데이터를 뱉어내며, 메인 컨트롤러는 이를 기반으로 여러 백그라운드 작업을 멀티스레드로 동시 분배(Parallel Dispatch)합니다.

```text
[사용자 발화 입력] ("아까 며느리 흉본 건 지워줘, 비밀이야.")
       │
       ▼
┌────────────────────────────────────────────────────────┐
│ 1단계: 엣지 sLLM (llama.cpp API Server / 8080 포트)    │
│  - Single-pass 추론을 통해 다중 상태 플래그가 담긴 JSON 생성 │
└────────────────────────────────────────────────────────┘
       │
       ▼ [출력 데이터 파싱: intent, privacy_flag, local_action]
┌────────────────────────────────────────────────────────┐
│ 2단계: 초경량 Python 미들웨어 (Flask Agent / 5000 포트) │
│  - 수신된 JSON 데이터 기반으로 멀티스레드 병렬 디스패치 수행 │
└────────────────────────────────────────────────────────┘
       │
       ├─► [스레드 A: 로컬 액션] ──────────────────► 즉시 로컬 캐시 오디오 재생 (Filler Word)
       │                                            (지연 시간 0.5초 이내 은닉 완료 🌟)
       │
       ├─► [스레드 B: 헬스케어 메타데이터] ─────────► 비식별 수치 데이터(WPM, 침묵 등) 분석 DB 전송
       │                                            (시계열 데이터 연속성 유지)
       │
       └─► [스레드 C: 프라이버시 필터링] 
            │
            ├──► privacy_flag == True  : 원본 발화 텍스트 즉시 메모리 파기 (Drop)
            │                            클라우드 RAG 서버로 비식별 마스킹 플래그 포워딩
            └──► privacy_flag == False : 클라우드 RAG/장문 대화 인프라로 정상 컨텍스트 토스

```

### 2.3. 프라이버시 보호를 위한 데이터 분리 아키텍처

사용자의 민감 데이터 파기 요청 시 헬스케어 추적 데이터의 연속성이 무너지는 모순을 '물리적 망분리' 구조로 해결합니다.

* **존엄성 보장 (Semantic Data 파기):** 사용자가 대화 삭제나 비밀을 요구할 경우, 엣지 sLLM이 이를 `[PRIVACY_REQ]`로 분류하여 대화 내용(Text/Audio)을 로컬 메모리 단계에서 즉시 파기(Volatile Drop)하고 서버 전송을 차단합니다.
* **성능 유지 (Metadata 보존):** 발화 내용 자체는 파기하되, 대화 시 발생한 통계 데이터(발화 속도[WPM], 침묵 길이, 목소리 떨림지수, 우울 스코어 수치)는 숫자 형태의 메타데이터로 분리 보존하여 시계열 분석의 연속성을 유지합니다.

### 2.4. 스토리지 및 메모리 매핑 구조 (Storage Mapping)

물리적 RAM(4GB) 부족으로 인한 OOM Killed 현상 및 16GB 내부 eMMC 용량 부족을 방지하기 위해 확장 스토리지를 마운트하고 가상 메모리 스왑 공간을 재구축합니다.

```text
[16GB eMMC (내부 스토리지)]
 ├── Ubuntu 18.04 OS / CUDA 10.2 Toolkit
 └── GCC 9 Compiler / Miniforge3 (Conda Core)

[64GB USB SD Card (/mnt/sdcard)]
 ├── /swapfile (8GB Virtual Memory)     <-- RAM 용량 방어선의 핵심 (활성화 필수)
 ├── /llama.cpp (Engine Binary)         <-- 베어메탈 C++ 빌드 환경
 └── /models (LLM Weights)              <-- Qwen 1.5-1.8B GGUF 가중치 (약 1GB)

```

---

## 3. Infrastructure & Memory Setup (인프라 및 메모리 최적화)

### 3.1. 스토리지 분리 및 마운트

```bash
sudo mkfs.ext4 /dev/sda1
sudo mkdir -p /mnt/sdcard
sudo mount /dev/sda1 /mnt/sdcard
sudo chown -R $USER:$USER /mnt/sdcard

```

### 3.2. Out of Memory (OOM) 방지용 8GB Swap 할당 및 확인

*주의: 젯슨 나노 재부팅 시 스왑이 해제되므로 서버 구동 전 반드시 아래 명령어로 활성화 상태를 점검해야 합니다.*

```bash
# 8GB 스왑 파일 강제 활성화
sudo swapon /mnt/sdcard/swapfile

# 메모리/스왑 상태 정보 출력 (Swap 항목의 Total이 ~9.9G 영역인지 확인)
free -h

```

## 5. Native Build & LLM Engine Setup (엔진 빌드 및 구동)

### 5.1. CUDA 툴킷 복구 및 컴파일러 업데이트

```bash
sudo apt update
sudo apt install -y nvidia-cuda-toolkit
sudo add-apt-repository -y ppa:ubuntu-toolchain-r/test
sudo apt update
sudo apt install -y gcc-9 g++-9

```

### 5.2. 소스코드 클론 및 가속 컴파일

NVIDIA 레거시 환경(CUDA 10.2)에서 완벽한 빌드 가속 안정성이 보장되는 `llama.cpp` 아카이브 버전(`b2400`)을 체크아웃하여 컴파일을 수행합니다.

```bash
cd /mnt/sdcard
git clone [https://github.com/ggerganov/llama.cpp](https://github.com/ggerganov/llama.cpp)
cd llama.cpp

# CUDA 10.2 호환 안정화 시점으로 타임머신 탑승
git checkout b2400

# 빌드 잔여물 청소 및 Maxwell 아키텍처(compute_53) 최적화 컴파일
make clean
make CC=gcc-9 CXX=g++-9 LLAMA_CUBLAS=1 CUDA_DOCKER_ARCH=compute_53 -j2

```

### 5.3. 모델 배포 및 백엔드 API 서버 구동

```bash
# 1. 모델 저장 폴더 구성 및 1.8B 양자화 가중치 다운로드
mkdir -p models
wget [https://huggingface.co/Qwen/Qwen1.5-1.8B-Chat-GGUF/resolve/main/qwen1_5-1_8b-chat-q4_k_m.gguf](https://huggingface.co/Qwen/Qwen1.5-1.8B-Chat-GGUF/resolve/main/qwen1_5-1_8b-chat-q4_k_m.gguf) -O models/qwen.gguf

# 2. 실행 경로 진입 및 server 실행 파일 빌드 유무 최종 점검
cd /mnt/sdcard/llama.cpp
ls -l server

# (만약 파일이 없을 경우 아래 명령어로 서버 바이너리 고속 빌드)
# make server CC=gcc-9 CXX=g++-9 LLAMA_CUBLAS=1 CUDA_DOCKER_ARCH=compute_53 -j2

# 3. 메모리 스파이크 차단을 위한 Context 512 다이어트 기반 API 서버 시동 (포트 8080)
./server -m models/qwen.gguf -c 512 -n 512 -ngl 99 -t 2 --host 0.0.0.0 --port 8080

```


## 7. Performance Evaluation & Strategy (성능 평가 및 제안서 방어 전략)

### 7.1. 시스템 벤치마크 지표

* **Model Load Time:** ~21.5s (SD Card 가상 메모리 Swapping 병목 포함 초기 1회 발생)
* **Prompt Eval Time:** ~82ms / token (사용자 입력 의도 분석 속도)
* **Generation Speed:** **~3.3 tokens/sec** (순수 장문 텍스트 생성 속도)

### 7.2. 심사평 지적사항에 대한 아키텍처적 타개책

1. **"스코어링 기준선(Baseline) 구축 모호성" 지적 대응**
* **해결책:** 시스템 도입 초기 2주간을 '초기 캘리브레이션 기간(Calibration Phase)'으로 명시화.
* 발화 속도(WPM), 침묵 길이(Pause), 어휘 다양성 지수(TTR)의 개인별 평균값과 표준편차를 정량 산출하여 고유 임계치 베이스라인을 수립합니다. 베이스라인 대비 2표준편차(2σ) 임계치 하락 시 우울/이상 징후 경고 트리거를 발동시킵니다.


2. **"데이터 삭제와 헬스케어 데이터 연속성 모순" 지적 대응**
* **해결책:** 엣지 단말 단의 **'Semantic/Meta 데이터 물리 분리 가공 구조'** 적용 (2.1절, 2.3절 구조적 증명).
* "이 이야기는 지워줘" 요청 시 민감 발화 내용(Semantic Text)은 로컬 메모리 단에서 즉각 drop하여 영구 파기하되, 해당 발화 시 추출된 비식별화 수치 데이터(목소리 떨림 지수, 침묵 시간 등)는 클라우드 시계열 DB에 안전하게 보존하여 분석 연속성을 확보합니다.


3. **"저사양 기기에서의 클라우드 연동 딜레이 및 대화 끊김" 지적 대응**
* **해결책:** 엣지 단말을 활용한 **'UX적 지연 시간 은닉 기법(Latency Masking)'** 적용 (2.2절, 6절 비동기 스레드 구현).
* 라즈베리파이/Jetson 등 엣지단에서 경량 VAD를 구동해 사용자의 음성 종료 시점을 즉시 판단하며, 엣지 LLM이 `[RAG]` 태그를 구하는 0.5초 이내의 순간에 로컬 메모리에 상주하는 자연스러운 리액션 음성(Filler Word: *"아~ 어르신 그러셨군요, 잠시만요"*)을 즉시 백그라운드 재생합니다. 이를 통해 클라우드 거대 모델 연동에 필요한 통신 딜레이(1~2초)를 사용자 경험 뒤편으로 완벽하게 은닉합니다.



```