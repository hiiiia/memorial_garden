from fastapi import FastAPI, BackgroundTasks, HTTPException, status, Header, Depends, UploadFile, File, Form
from pydantic import BaseModel
import httpx
import os
import shutil
import uuid
import json
import asyncio
import numpy as np
import librosa

from openai import AsyncOpenAI 

from app.config import settings
from app.utils.backup import save_failed_callback_to_local
from app.deps import validate_ai_secret_token


app = FastAPI(title="기억정원 AI Orchestrator Server")

# ==========================================
# 1. 환경 변수 및 글로벌 클라이언트 설정
# ==========================================
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
AI_SECRET_TOKEN = os.getenv("AI_SECRET_TOKEN", "my_super_secret_ai_token")

# GX10 서버 (순수 LLM 추론 엔진) 연결
client = AsyncOpenAI(
    base_url="http://codu.ddns.net:11434/v1",
    api_key="ollama"
)
LLM_MODEL = "gemma4:12b"           # 무거운 심층 분석용
LIGHT_LLM_MODEL = "qwen2.5:7b"     # 엣지 실시간 라우팅용

# ==========================================
# 2. 데이터 스키마
# ==========================================
class EdgeRouteRequest(BaseModel):
    user_id: str 
    text: str
    memory_context: str

class GreetingRequest(BaseModel):
    name: str
    time_context: str
# ==========================================
# 3. 유틸리티 및 오디오 분석 함수
# ==========================================
async def send_failed_callback(callback_url: str, user_id: str, headers: dict, error_code: str, error_msg: str, job_id: str):
    """실패 상태를 백엔드로 전송하거나 로컬에 백업합니다."""
    error_callback_body = {
        "user_id": user_id, "status": "FAILED", "error_code": error_code, "error_message": error_msg,
        "analysis_data": {
            "risk_score": 0.0, "primary_emotion": "neutral", "llm_summary": f"[{error_code}] {error_msg}",
            "reply_text": "분석을 완료하지 못했습니다.", "stt_text": "", "image_url": "",
            "depression_score": 0.0, "cognitive_decline_score": 0.0, "care_level": "NORMAL"
        }
    }
    try:
        async with httpx.AsyncClient() as http_client:
            print(f"[AI Error Handler] FAILED 콜백 전송 중... ({error_code})")
            res = await http_client.post(callback_url, json=error_callback_body, headers=headers)
            res.raise_for_status()
    except Exception as callback_err:
        print(f"[AI Fatal Error] FAILED 콜백 전송 실패: {str(callback_err)}")
        save_failed_callback_to_local(job_id=job_id, user_id=user_id, payload=error_callback_body, error_reason=str(callback_err))


async def generate_diary_image(image_prompt: str, job_id: str) -> str:
    """실제 AI 이미지 생성 API 호출 및 AI 서버 URL 직접 반환"""
    if not image_prompt: return ""
    print(f"[AI Image] 실제 API로 이미지 생성을 요청합니다. 프롬프트: {image_prompt[:20]}...")
    
    # 1. 방금 구축한 실제 API 엔드포인트와 규격 세팅
    api_url = "http://codu.ddns.net:11435/v1/images/generations"
    payload = {
        "prompt": image_prompt,
        "model": "flux_schnell"
    }
    
    try:
        # LLM 번역 + 이미지 생성이 있으므로 타임아웃을 넉넉히(120초) 줍니다.
        async with httpx.AsyncClient(timeout=120.0) as http_client:
            
            # Step 1: 서버에 이미지 생성 요청 (POST)
            response = await http_client.post(api_url, json=payload)
            response.raise_for_status()
            
            # Step 2: 응답 JSON에서 완성된 이미지의 URL 추출
            result_data = response.json()
            generated_image_url = result_data["data"][0]["url"]
            print(f"[AI Image] 생성 완료! AI 서버의 이미지 URL을 반환합니다: {generated_image_url}")
            
        #  다운로드하지 않고, AI 서버의 URL을 그대로 반환
        return generated_image_url
        
    except Exception as e:
        print(f"[AI Image Error] 실제 이미지 생성 실패: {str(e)}")
        return ""
    
def _extract_biomarkers_sync(wav_path: str) -> dict:
    """[동기 함수] 오디오 파형에서 바이오마커 수치를 추출합니다."""
    try:
        y, sr = librosa.load(wav_path, sr=16000)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        rms = librosa.feature.rms(y=y)
        pause_ratio = float(np.sum(rms < 0.02) / len(rms[0])) if len(rms[0]) > 0 else 0.0
        pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
        valid_pitches = pitches[magnitudes > np.median(magnitudes)]
        pitch_variance = float(np.var(valid_pitches)) if len(valid_pitches) > 0 else 0.0

        return {
            "speech_rate": float(tempo),
            "pause_ratio": float(pause_ratio),
            "pitch_variance": float(pitch_variance)
        }
    except Exception as e:
        print(f"[AI Server] 음향 추출 실패: {e}")
        return {"speech_rate": 0.0, "pause_ratio": 0.0, "pitch_variance": 0.0}

# ==========================================
# 4. 비동기 백그라운드 파이프라인 (무거운 작업)
# ==========================================
async def process_audio_and_shred(file_path: str, user_id: str, stt_text: str, job_id: str, callback_url: str):
    """오디오 파형을 분석하고, Ollama를 호출한 뒤 파일을 파기합니다."""
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {settings.AI_SECRET_TOKEN}"}
    print(f"[AI Server] === 심층 분석 파이프라인 시작 (Job: {job_id}) ===")
    
    try:
        # [단계 A] 음향 수치 추출 (CPU 블로킹 방지를 위해 백그라운드 스레드로 실행)
        biomarkers = await asyncio.to_thread(_extract_biomarkers_sync, file_path)
        print(f"[AI Server] 음향 수치 추출 완료: {biomarkers}")
        
        # [단계 B] 텍스트와 추출된 수치를 융합하여 Ollama에 전송
        prompt = f"""
당신은 노인 회상치료(Reminiscence Therapy) 전문가이자 정서 케어 AI입니다.
아래 제공된 대화 기록과 오디오 파형에서 추출된 음향 바이오마커 수치를 종합하여 심리 상태를 평가하세요.

[사용자 대화 원문]
{stt_text}

[음향 바이오마커 수치 (분석 참고용)]
- 말하기 속도 (speech_rate): {biomarkers['speech_rate']:.2f} (인지 저하가 있을수록 느려짐)
- 침묵 비율 (pause_ratio): {biomarkers['pause_ratio']:.2f} (우울/인지 저하 시 수치 증가)
- 음역대 변화율 (pitch_variance): {biomarkers['pitch_variance']:.2f} (우울증 심화 시 수치 하락)

[분석 목표 및 규칙]
1. 위 데이터들을 종합하여 risk_score, depression_score, cognitive_decline_score를 0.0 ~ 1.0 사이로 평가하세요.
2. primary_emotion (주된 감정)을 단어로 출력하세요.
3. llm_summary: 어르신의 대화 내용 요약과 더불어, 음향 바이오마커로 나타난 발화 상태(말하기 속도, 침묵 빈도 등), 인지 능력 저하 징후, 그리고 정서적 건강 상태(우울감/불안)에 대한 종합적인 건강 평가 소견을 2~3문장으로 상세히 작성하세요.
4. diary_text: 따뜻한 그림일기 본문을 1~2문장으로 작성하세요.
5. image_prompt: 그림일기 삽화를 위한 영어 프롬프트(수채화 스타일 강조)를 작성하세요.
6. care_level: NORMAL, WATCH, WARNING, EMERGENCY 중 하나를 선택하세요.

반드시 아래 JSON 형식으로만 응답하세요.
{{
"risk_score": 0.0,
"depression_score": 0.0,
"cognitive_decline_score": 0.0,
"primary_emotion": "neutral",
"llm_summary": "",
"diary_text": "",
"image_prompt": "",
"care_level": "NORMAL"
}}
"""
        response = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Output only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        analysis_result = json.loads(response.choices[0].message.content)
        print("[AI Server] LLM 심층 융합 분석 완료")
        
        image_url = await generate_diary_image(analysis_result.get("image_prompt", ""), job_id)

        # [단계 C] 백엔드(보호자 DB)로 분석 완료된 JSON 데이터 전송
        callback_body = {
            "user_id": user_id, "status": "COMPLETED", "error_code": None, "error_message": None,
            "analysis_data": {
                "risk_score": float(analysis_result.get("risk_score", 0.0)),
                "primary_emotion": analysis_result.get("primary_emotion", "neutral"),
                "llm_summary": analysis_result.get("llm_summary", ""),  # 원문을 바탕으로 추출된 고도화된 헬스케어 종합 소견 요약
                "image_url": image_url, 
                "diary_text": analysis_result.get("diary_text", ""),
                "depression_score": float(analysis_result.get("depression_score", 0.0)),
                "cognitive_decline_score": float(analysis_result.get("cognitive_decline_score", 0.0)),
                "care_level": analysis_result.get("care_level", "NORMAL"),
                "speech_rate": float(biomarkers.get("speech_rate", 0.0)),
                "pause_ratio": float(biomarkers.get("pause_ratio", 0.0)),
                "pitch_variance": float(biomarkers.get("pitch_variance", 0.0))
            }
        }
        
        async with httpx.AsyncClient() as http_client:
            res = await http_client.post(callback_url, json=callback_body, headers=headers)
            res.raise_for_status()
            print(f"[AI Server] 백엔드 전송 완료! 상태코드: {res.status_code}")

    except Exception as e:
        print(f"[AI Server] 오디오 처리 에러: {e}")
        await send_failed_callback(callback_url, user_id, headers, "LLM_ANALYSIS_FAILED", str(e), job_id)
        
    finally:
        # [보안 핵심] 무조건 실행되는 finally 블록에서 오디오 원본 영구 파기
        if os.path.exists(file_path):
            os.remove(file_path)
            print("[보안] 인메모리 오디오 원본 파일 파기 완료. (데이터 휘발 성공)")
            
# ==========================================
# 5. API 엔드포인트
# ==========================================
@app.get("/")
def read_root():
    return {"message": "Welcome to AI Analysis Server (Orchestrator Edition)"}

@app.post("/api/v1/analyze/audio", status_code=status.HTTP_202_ACCEPTED, summary="비동기 오디오 딥러닝 분석 및 파기")
async def analyze_audio_background(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),         
    user_id: str = Form(...),             
    stt_text: str = Form(...),
    _ = Depends(validate_ai_secret_token)
):
    job_id = uuid.uuid4().hex
    temp_file_path = f"/tmp/{job_id}_{file.filename}"
    
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    print(f"[AI Server] 백그라운드 분석용 오디오 수신 완료: {file.filename}")

    background_tasks.add_task(
        process_audio_and_shred, 
        file_path=temp_file_path, 
        user_id=user_id, 
        stt_text=stt_text, 
        job_id=job_id,
        callback_url=f"{settings.BACKEND_URL}api/v1/callbacks/jobs/analyze-result"
    )
    return {"message": "Audio processing started in background."}


@app.post("/api/v1/edge/route", summary="Edge Device Real-time Routing & Orchestration")
async def process_edge_routing(request: EdgeRouteRequest, _ = Depends(validate_ai_secret_token)):
    raw_text = request.text
    user_id = request.user_id 
    memory_context = request.memory_context
    
    print(f"[Edge Request] 발화 수신: '{raw_text}'")
    if memory_context:
        print(f"[Edge Context] 로컬 기억 수신: '{memory_context[:30]}...'")

    routing_prompt = f"""
당신은 반려 로봇 '기억정원'의 공감 대화 에이전트이자 보안 라우터입니다.
아래 [입력 데이터]를 분석하여 지정된 [JSON 출력 규칙]에 맞게 응답하세요.

[입력 데이터]
- 어르신 현재 발화: "{raw_text}"
- 시스템 참고용 과거 기억(엣지 제공): "{memory_context if memory_context else '관련된 과거 기록이 없습니다.'}"

[JSON 출력 규칙]
1. intent: "SIMPLE_CHAT" (고정)
2. privacy_flag: 발화에 가족, 금전, 건강, 비밀 등의 민감한 내용이 포함되면 true, 일상 대화면 false.
3. safe_text: privacy_flag가 true면 구체적 명사를 지우고 상황만 요약. false면 발화 원문 그대로 복사.
4. save_flag: 발화가 질문("언제였지?")이거나 단순 하소연이면 false. 완전히 새로운 사실이나 사건일 때만 true.
5. local_action: "filler_hmm.mp3" 등 상황에 맞는 추임새 (없으면 null).
6. local_reply: 1~2문장의 따뜻한 답변. 
   - [주의 1] 반드시 [시스템 참고용 과거 기억]에 있는 사실(Fact)만 언급하세요. 왜곡 금지.
   - [주의 2] 반드시 정중하고 다정한 존댓말만 사용하세요.
   - [과거 기억]이 있다면 해당 날짜와 내용을 자연스럽게 대화에 녹이세요. (괄호 출력 금지)
   - [과거 기억]이 없으면 "제가 기억 상자를 조금 더 찾아보고 말씀드릴게요."라고 하세요.

[Few-Shot 예시 - 이 형식을 완벽히 따르세요]
사용자 발화: "우리 며느리랑 돈 때문에 서운했던 게 언제였더라?"
참고용 기억: "어르신의 과거 기억 (날짜: 2026-05-10): 며느리가 생활비를 너무 적게 줘서 서운해."
출력:
{{
  "intent": "SIMPLE_CHAT",
  "privacy_flag": true,
  "safe_text": "가족 간 금전 문제로 인한 서운함 과거 기억 질문",
  "save_flag": false,
  "local_action": "filler_hmm.mp3",
  "local_reply": "어르신, 지난 5월 10일에 며느님이 생활비를 적게 주셔서 많이 속상해하셨잖아요. 그 생각에 마음이 또 무거워지셨군요. 제가 다 들어드릴게요."
}}
"""
    try:
        response = await client.chat.completions.create(
            model=LIGHT_LLM_MODEL,
            messages=[
                {"role": "system", "content": "오직 JSON 형식으로만 응답하세요."}, 
                {"role": "user", "content": routing_prompt}
            ],
            temperature=0.3, 
            response_format={"type": "json_object"}, 
            timeout=8.0
        )
        routing_data = json.loads(response.choices[0].message.content)
        print(f"[Orchestration 완료] 생성된 응답: {routing_data['local_reply'][:20]}...")
        
    except Exception as e:
        print(f"[AI 서버 라우팅 실패]: {e}")
        return {
            "intent": "SIMPLE_CHAT", 
            "privacy_flag": False, 
            "safe_text": raw_text, 
            "save_flag": False,
            "local_action": None, 
            "local_reply": "어르신, 제가 방금 하신 말씀을 잘 이해하지 못했어요. 다시 한 번 말씀해 주시겠어요?"
        }

    return routing_data



@app.post("/api/v1/generate-greeting")
async def generate_greeting(
    request: GreetingRequest, 
    _ = Depends(validate_ai_secret_token)
):
    print(f"🧠 [AI Server] {request.name} 어르신을 위한 {request.time_context} 프롬프트 생성 중...")

    # System Prompt: JSON 포맷 강제 및 페르소나 부여
    system_prompt = """
    You are a helpful assistant. Output only valid JSON.
    당신은 독거 어르신에게 다정하고 친근하게 말을 거는 손주 같은 인공지능 로봇입니다.
    반드시 "greeting_text"라는 키를 가진 JSON 객체로만 응답하세요.
    """

    # User Prompt: 구체적인 상황 정보 및 지침 전달
    user_prompt = f"""
    어르신의 이름은 '{request.name}'입니다.
    지금 시간대는 {request.time_context}입니다.

    [지침]
    1. 어르신에게 존댓말을 사용하고, 아주 다정하고 살갑게 말해주세요.
    2. 현재 시간대({request.time_context})에 맞는 자연스러운 날씨나 식사 관련 안부를 포함해주세요.
    3. 너무 길지 않게 2~3문장으로 간결하게 작성해주세요.
    4. 어르신이 대답하기 쉽도록 가벼운 질문으로 마무리해주세요.
    5. "로봇입니다", "무엇을 도와드릴까요" 같은 기계적인 표현은 절대 금지합니다.
    """

    try:
        response = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # JSON 파싱
        analysis_result = json.loads(response.choices[0].message.content)
        
        # 'greeting_text' 키 값 추출
        greeting_text = analysis_result.get("greeting_text", "")
        
        print(f"[AI Server] LLM 안부 메시지 생성 완료: {greeting_text}")
        
        return {"greeting_text": greeting_text}
        
    except Exception as e:
        print(f"🚨 [AI Server] LLM 통신 또는 JSON 파싱 실패: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate greeting via GX10")
    
    
    