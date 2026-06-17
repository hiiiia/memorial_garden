```markdown
# 📄 Technical Specification: Jetson Nano 기반 하이브리드 Edge AI 및 라우팅 파이프라인

## 1. Overview (개요)
본 문서는 NVIDIA Jetson Nano B01 환경에서 발생할 수 있는 하드웨어적 한계(16GB eMMC, 4GB RAM)와 레거시 소프트웨어 종속성(CUDA 10.2, GCC 7) 문제를 극복하고, Edge 환경에 최적화된 소형 LLM(sLLM)을 Native 환경에서 구동하기 위한 인프라 구축 및 모델 배포 파이프라인을 정의합니다. 

더불어, 저사양 기기에서 대형 모델 연동 시 발생하는 지연(Latency) 문제와 사용자 프라이버시 보호 요구사항을 구조적으로 타개하기 위한 **'하이브리드 인텐트 라우팅(Hybrid Intent Routing)'** 및 **'데이터 분리 처리(Semantic vs Meta)'** 전략을 통합 명세합니다.

- **목적:** Edge 단말 단에서의 조건부 RAG 판단, 실시간 하드웨어 통제 및 지연 시간 은닉
- **주요 기술 스택:** Ubuntu 18.04, CUDA 10.2, C++ (GCC 9), llama.cpp, GGUF 양자화 모델, VAD (Voice Activity Detection)

---

## 2. System Architecture (시스템 아키텍처)

본 프로젝트는 초기 Docker 기반 배포를 기획하였으나, 레거시 JetPack(4.6) 버전 파편화로 인해 최종적으로 **Native (Bare Metal) 아키텍처**로 전환하여 시스템 오버헤드를 제거하고 성능을 극대화했습니다.

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

### 2.2. 하이브리드 인텐트 라우팅 및 지연 은닉 파이프라인

엣지 단말은 실시간성 제어 및 인텐트 분류기(Dispatcher) 역할을 수행하며, 무거운 질의 및 장문 대화는 클라우드 인프라로 가속 위임합니다.

```text
[사용자 발화 입력]
       │
       ▼
┌────────────────────────────────────────────────────────┐
│ 1단계: 엣지 코어 루틴 (Local Edge - Jetson Nano)      │
│  - 경량 VAD 가동: 정확한 침묵/음성 감지로 네트워크 절약 │
│  - sLLM (Qwen 1.8B) 추론: 인텐트(의도) 분석 및 라우팅   │
└────────────────────────────────────────────────────────┘
       │
       ├─► [의도: 기기 제어 및 단답형 상태 확인] 
       │    │
       │    ▼ (지연 시간: ~0.5초 이내)
       │   ┌──────────────────────────────────────────────┐
       │   │ 2단계 (A): 로컬 제어 (Local Execution)        │
       │   │  - 즉시 구조화된 JSON 제어 코드 파싱 및 실행  │
       │   └──────────────────────────────────────────────┘
       │
       └─► [의도: 심층 질의 / RAG 기반 장문 대화] 
            │
            ▼ (지연 시간 은닉 기법 동시 가동 🌟)
           ┌──────────────────────────────────────────────┐
           │ 2단계 (B): 딜레이 은닉 및 클라우드 파이프라인  │
           │  - 로컬 캐시 추임새 오디오(Filler Word) 즉시 재생│
           │  - 상위 클라우드 LLM 인프라로 컨텍스트 토스   │
           │  - 척(Chunk) 단위 실시간 스트리밍 답변 반환   │
           └──────────────────────────────────────────────┘

```

### 2.3. 프라이버시 보호를 위한 데이터 분리 아키텍처

사용자의 민감 데이터 파기 요청 시 헬스케어 추적 데이터의 연속성이 무너지는 모순을 '물리적 망분리' 구조로 해결합니다.

* **존엄성 보장 (Semantic Data 파기):** 사용자가 대화 삭제나 비밀을 요구할 경우, 엣지 sLLM이 이를 `[PRIVACY_REQ]`로 분류하여 대화 내용(Text/Audio)을 로컬 메모리 단계에서 즉시 파기(Volatile Drop)하고 서버 전송을 차단합니다.
* **성능 유지 (Metadata 보존):** 발화 내용 자체는 파기하되, 대화 시 발생한 통계 데이터(발화 속도[WPM], 침묵 길이, 목소리 떨림지수, 우울 스코어 수치)는 숫자 형태의 메타데이터로 분리 보존하여 시계열 분석의 연속성을 유지합니다.

### 2.4. 스토리지 및 메모리 매핑 구조 (Storage Mapping)

16GB eMMC의 용량 한계와 4GB RAM의 OOM(Out of Memory) 현상을 방지하기 위해 I/O 병목이 적은 외부 USB 스토리지를 주 작업 공간으로 맵핑합니다.

```text
[16GB eMMC] (내부 고속 스토리지)
 ├── Ubuntu 18.04 OS
 ├── CUDA 10.2 Toolkit
 └── GCC 9 Compiler & Tools

[64GB USB SD Card] (/mnt/sdcard)
 ├── /swapfile (8GB Virtual Memory)     <-- 가상 메모리 확보를 통한 RAM OOM 방지
 ├── /llama.cpp (Source Code & Engine)  <-- 베어메탈 빌드 환경 및 실행 바이너리
 └── /models (LLM Weights)              <-- Qwen 1.5-1.8B 양자화 가중치 (약 1GB)

```

---

## 3. Infrastructure Setup (인프라 최적화)

### 3.1. 스토리지 분리 및 마운트

외장 USB SD 카드를 주 작업 공간으로 포맷 및 권한 매핑을 진행합니다.

```bash
sudo mkfs.ext4 /dev/sda1
sudo mkdir -p /mnt/sdcard
sudo mount /dev/sda1 /mnt/sdcard
sudo chown -R $USER:$USER /mnt/sdcard

```

### 3.2. Out of Memory (OOM) 방지용 Swap 할당

가중치 적재 및 컴파일 시 보드가 다운되는 현상을 막기 위해 8GB 크기의 스왑 공간을 활성화합니다.

```bash
sudo fallocate -l 8G /mnt/sdcard/swapfile
sudo chmod 600 /mnt/sdcard/swapfile
sudo mkswap /mnt/sdcard/swapfile
sudo swapon /mnt/sdcard/swapfile

```

---

## 4. Native Build Environment (빌드 환경 구성)

### 4.1. CUDA Toolkit 복구

경량 커스텀 OS 빌드 시 제거되었던 `nvcc` 및 기본 CUDA 개발 도구를 시스템에 재구축합니다.

```bash
sudo apt update
sudo apt install -y nvidia-cuda-toolkit

```

### 4.2. GCC 9 컴파일러 툴체인 업데이트

구형 컴파일러(GCC 7) 환경에서 최신 ARM NEON 벡터 연산(i-quants) 소스 빌드 시 발생하는 문법 에러(`incompatible types`)를 해결하기 위해 상위 툴체인을 도입합니다.

```bash
sudo add-apt-repository -y ppa:ubuntu-toolchain-r/test
sudo apt update
sudo apt install -y gcc-9 g++-9

```

---

## 5. LLM Engine Compilation (엔진 빌드)

NVIDIA 레거시 환경(CUDA 10.2)에서 완벽한 가속 안정성을 보장하는 `llama.cpp` 아카이브 버전(`b2400`)을 체크아웃하여 컴파일을 수행합니다.

```bash
cd /mnt/sdcard
git clone [https://github.com/ggerganov/llama.cpp](https://github.com/ggerganov/llama.cpp)
cd llama.cpp

# CUDA 10.2 호환 안정화 시점으로 타임머신 탑승
git checkout b2400

# 이전 실패 잔여물 청소 및 Maxwell 아키텍처(compute_53) 최적화 컴파일 시작
make clean
make CC=gcc-9 CXX=g++-9 LLAMA_CUBLAS=1 CUDA_DOCKER_ARCH=compute_53 -j2

```

---

## 6. Model Deployment & Inference (모델 배포 및 추론)

### 6.1. 모델 가중치 다운로드

리소스 제약 환경에서 제어 명령어 구조화 및 인텐트 분류 작업의 정확도가 검증된 1.8B 파라미터 양자화 모델을 확보합니다.

```bash
mkdir -p models
wget [https://huggingface.co/Qwen/Qwen1.5-1.8B-Chat-GGUF/resolve/main/qwen1_5-1_8b-chat-q4_k_m.gguf](https://huggingface.co/Qwen/Qwen1.5-1.8B-Chat-GGUF/resolve/main/qwen1_5-1_8b-chat-q4_k_m.gguf) -O models/qwen.gguf

```

### 6.2. 대화형 지시 모드(Instruct) 런타임 구동

모델이 챗 템플릿 구조를 엄격히 준수하여 분기 태그를 반환할 수 있도록 대화형 인프라 모드를 활성화하여 실행합니다.

```bash
# 모든 연산 레이어를 GPU로 오프로딩(-ngl 99) 및 컨텍스트 최적화
./main -m models/qwen.gguf -n 512 -ngl 99 -c 1024 -i -ins

```

---

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
* **해결책:** 엣지 단말 단의 **'Semantic/Meta 데이터 물리 분리 가공 구조'** 적용 (2.3절 참조).
* "이 이야기는 지워줘" 요청 시 민감 발화 내용(Semantic Text)은 로컬 메모리 단에서 즉각 drop하여 영구 파기하되, 해당 발화 시 추출된 비식별화 수치 데이터(목소리 떨림 지수, 침묵 시간 등)는 클라우드 시계열 DB에 안전하게 보존하여 분석 연속성을 확보합니다.


3. **"저사양 기기에서의 클라우드 연동 딜레이 및 대화 끊김" 지적 대응**
* **해결책:** 엣지 단말을 활용한 **'UX적 지연 시간 은닉 기법(Latency Masking)'** 적용.
* 라즈베리파이/Jetson 등 엣지단에서 경량 VAD를 구동해 사용자의 음성 종료 시점을 즉시 판단하며, 엣지 LLM이 `[RAG]` 태그를 구하는 0.5초 이내의 순간에 로컬 메모리에 상주하는 자연스러운 리액션 음성(Filler Word: *"아~ 어르신 그러셨군요, 잠시만요"*)을 즉시 백그라운드 재생합니다. 이를 통해 클라우드 거대 모델 연동에 필요한 통신 딜레이(1~2초)를 사용자 경험 뒤편으로 완벽하게 은닉합니다.



```

```