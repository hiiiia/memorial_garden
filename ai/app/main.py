from fastapi import FastAPI, BackgroundTasks, HTTPException, status, Header, Depends
from pydantic import BaseModel
import httpx
import os
import json
import asyncio
import subprocess
import urllib.parse
import numpy as np

# STT 모델
from faster_whisper import WhisperModel
from openai import AsyncOpenAI 

from app.config import settings
from app.utils.backup import save_failed_callback_to_local

app = FastAPI(title="기억정원 AI Orchestrator Server")

# ==========================================
# 1. 환경 변수 및 글로벌 클라이언트 설정
# ==========================================
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
AI_SECRET_TOKEN = os.getenv("AI_SECRET_TOKEN", "my_super_secret_ai_token")

# 🌟 모든 통신을 비동기로 처리하기 위해 AsyncOpenAI 사용
client = AsyncOpenAI(
    base_url="http://codu.ddns.net:11434/v1",
    api_key="ollama"
)
LLM_MODEL = "gemma4:12b"           # 무거운 심층 분석용
LIGHT_LLM_MODEL = "qwen2.5:3b"     # 엣지 실시간 라우팅용
EMBEDDING_MODEL = "nomic-embed-text"

print("🎙️ Faster-Whisper STT 모델 로딩 중...")
whisper_model = WhisperModel("base", device="cpu", compute_type="int8")

# ==========================================
# 2. 데이터 스키마 및 보안 의존성 정의
# ==========================================
class AnalysisTriggerRequest(BaseModel):
    job_id: str
    user_id: str
    file_path: str
    callback_url: str

class FastChatCallbackRequest(BaseModel):
    job_id: str
    user_text: str
    memory_context: str
    callback_url: str

class EdgeRouteRequest(BaseModel):
    user_id: str 
    text: str

def verify_api_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized. Missing token.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token != settings.AI_SECRET_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized. Invalid token.")
    return token

# ==========================================
# 🛠️ 유틸리티 함수 모음
# ==========================================
async def send_failed_callback(callback_url: str, user_id: str, headers: dict, error_code: str, error_msg: str, job_id: str):
    """실패 상태를 백엔드로 전송하거나 로컬에 백업합니다."""
    error_callback_body = {
        "user_id": user_id, "status": "FAILED", "error_code": error_code, "error_message": error_msg,
        "analysis_data": {
            "risk_score": 0.0, "primary_emotion": "neutral", "llm_summary": f"[{error_code}] {error_msg}",
            "reply_text": "죄송합니다. 서버 문제로 분석을 완료하지 못했습니다. 잠시 후 다시 시도해 주세요.",
            "stt_text": "", "image_url": ""
        }
    }
    try:
        async with httpx.AsyncClient() as http_client:
            print(f"\n[AI Error Handler] FAILED 콜백 전송 중... ({error_code})")
            res = await http_client.post(callback_url, json=error_callback_body, headers=headers)
            res.raise_for_status()
    except Exception as callback_err:
        print(f"\n[AI Fatal Error] FAILED 콜백 전송 실패: {str(callback_err)}")
        save_failed_callback_to_local(job_id=job_id, user_id=user_id, payload=error_callback_body, error_reason=str(callback_err))

def extract_audio_with_ffmpeg(file_path: str, target_sr: int = 16000) -> np.ndarray:
    """[동기 함수] FFmpeg로 오디오를 추출합니다."""
    print(f"\n[FFmpeg] 🎬 오디오 추출 시작: {file_path}")
    command = ["ffmpeg", "-i", file_path, "-f", "f32le", "-ac", "1", "-ar", str(target_sr), "-loglevel", "quiet", "-"]
    try:
        out, _ = subprocess.Popen(command, stdout=subprocess.PIPE).communicate()
    except Exception as e:
        raise RuntimeError(f"[FFmpeg Error] 실행 중 예외 발생: {e}")
    return np.frombuffer(out, np.float32).flatten()

async def get_embedding(text: str) -> list[float]:
    """Ollama를 통해 텍스트의 벡터 임베딩을 생성합니다."""
    try:
        response = await client.embeddings.create(model=EMBEDDING_MODEL, input=text)
        return response.data[0].embedding
    except Exception as e:
        print(f"❌ [Embedding Error] 임베딩 생성 실패: {e}")
        raise HTTPException(status_code=500, detail="임베딩 생성 실패")
    
async def fetch_memories_from_backend(query_vector: list[float], user_id: str) -> list[str]:
    """백엔드 서버의 벡터 검색 API를 호출하여 과거 기억 리스트를 받아옵니다."""
    search_url = f"{BACKEND_URL}/search/{user_id}"
    payload = {"query_vector": query_vector, "limit": 3}
    try:
        async with httpx.AsyncClient() as http_client:
            resp = await http_client.post(search_url, json=payload, timeout=5.0)
            if resp.status_code == 200:
                return resp.json().get("memories", [])
            return []
    except Exception as e:
        print(f"❌ [Backend Connection Failed] 백엔드 통신 실패: {e}")
        return []

async def generate_diary_image(image_prompt: str, job_id: str, max_retries: int = 3, base_delay: int = 5) -> str:
    """더미 이미지 다운로드 (테스트용)"""
    if not image_prompt: return ""
    print("\n[AI Image] 🎨 테스트용 임시(Dummy) 이미지를 다운로드합니다...")
    dummy_url = "https://placehold.co/512x512/e2e8f0/475569.png?text=Picture+Diary+Test"
    save_dir = "/app/uploads/diary_images"
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, f"diary_{job_id}.png")
    try:
        async with httpx.AsyncClient() as http_client:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = await http_client.get(dummy_url, headers=headers, timeout=30.0)
            response.raise_for_status()
            with open(save_path, "wb") as f:
                f.write(response.content)
        return f"http://localhost:8000/static/diary_images/diary_{job_id}.png"
    except Exception as e:
        print(f"[AI Image Error] 더미 이미지 다운로드 실패: {str(e)}")
        return ""

# ==========================================
# 3. 비동기 백그라운드 파이프라인 (무거운 작업)
# ==========================================
async def process_audio_and_callback(job_id: str, user_id: str, file_path: str, callback_url: str):
    if not os.path.exists(file_path):
        return

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {settings.AI_SECRET_TOKEN}"}
    print(f"\n[AI] === {LLM_MODEL} 심층 분석 파이프라인 시작 ===")
    
    # 🌟 1. CPU 블로킹 방지: STT 추출을 백그라운드 스레드(to_thread)로 던집니다.
    try:
        audio_array = await asyncio.to_thread(extract_audio_with_ffmpeg, file_path)
        # Faster-Whisper 처리도 스레드로 분리
        segments, _ = await asyncio.to_thread(whisper_model.transcribe, audio_array, beam_size=5, language="ko")
        quick_stt_text = " ".join([segment.text for segment in segments]).strip()
        print(f"[AI STT 결과] {quick_stt_text}")

        past_memories = []
        if quick_stt_text:
            query_vector = await get_embedding(quick_stt_text)
            past_memories = await fetch_memories_from_backend(query_vector, user_id)
            print(f"[AI] ✅ 관련된 과거 기억 {len(past_memories)}개 발견!")
    except Exception as e:
        print(f"[AI Warning] STT/RAG 에러 (기억 없이 진행): {e}")
        quick_stt_text = ""
        past_memories = []

    memory_context = "\n- ".join(past_memories) if past_memories else "이전 대화와 관련된 특별한 기억이 없습니다."
    
    # 🌟 2. LLM 텍스트 분석 (비동기 await 필수)
    prompt = f"""(기존 심층 분석 프롬프트 동일 - 생략 없이 그대로 유지)
    [과거 기억 참고]\n{memory_context}\n[사용자 대화]\n{quick_stt_text}""" # (실제 코드는 프롬프트 원문 삽입)
    
    # 간결함을 위해 프롬프트 원문은 개발자님이 기존 코드대로 유지하시면 됩니다. (여기에 그대로 복붙)
    
    try:
        print("\n[AI] 심층 분석 LLM 호출 중...")
        response = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Output only valid JSON."},
                {"role": "user", "content": prompt} # 프롬프트는 기존 내용 그대로 채워주세요
            ],
            response_format={"type": "json_object"}
        )
        analysis_result = json.loads(response.choices[0].message.content)
        print("[AI] ✅ 분석 성공!")
    except Exception as e:
        print(f"[AI Critical Error] 분석 실패: {e}")
        await send_failed_callback(callback_url, user_id, headers, "LLM_ANALYSIS_FAILED", "텍스트 분석 응답 오류", job_id)
        return

    # 🌟 3. 벡터 임베딩 (비동기)
    vector_embedding = [0.0] * 3072
    if analysis_result.get("llm_summary"):
        try:
            vector_embedding = await get_embedding(analysis_result["llm_summary"])
        except:
            pass

    # 🌟 4. 그림일기 (비동기)
    image_url = await generate_diary_image(analysis_result.get("image_prompt", ""), job_id)

    # 🌟 5. 콜백 전송
    callback_body = {
        "user_id": user_id, "status": "COMPLETED", "error_code": None, "error_message": None,
        "analysis_data": {
            "risk_score": float(analysis_result.get("risk_score", 0.0)),
            "primary_emotion": analysis_result.get("primary_emotion", "neutral"),
            "llm_summary": analysis_result.get("llm_summary", ""),
            "reply_text": analysis_result.get("reply_text", "오늘의 이야기를 소중히 기록해 두었습니다."),
            "stt_text": quick_stt_text,
            "image_url": image_url, 
            "depression_score": float(analysis_result.get("depression_score", 0.0)),
            "cognitive_decline_score": float(analysis_result.get("cognitive_decline_score", 0.0)),
            "care_level": analysis_result.get("care_level", "NORMAL"),
            "vector_embedding": vector_embedding 
        }
    }
    
    try:
        async with httpx.AsyncClient() as http_client:
            res = await http_client.post(callback_url, json=callback_body, headers=headers)
            res.raise_for_status()
            print(f"[AI] ✅ 백엔드 전송 완료! 상태코드: {res.status_code}")
    except Exception as e:
        save_failed_callback_to_local(job_id=job_id, user_id=user_id, payload=callback_body, error_reason="COMPLETED 콜백 전송 실패")

async def process_fast_chat_and_callback(payload: dict):
    prompt = f"[과거 기억]\n{payload['memory_context']}\n[어르신 말씀]\n{payload['user_text']}"
    try:
        response = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "system", "content": "Output only valid JSON."}, {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}, temperature=0.7
        )
        ai_answer = json.loads(response.choices[0].message.content).get("reply_text", "잘 못 들었어요.")
    except:
        ai_answer = "제가 잠시 딴생각을 하느라 못 들었어요."

    async with httpx.AsyncClient() as http_client:
        await http_client.post(payload["callback_url"], json={"status": "COMPLETED", "reply_text": ai_answer, "job_id": payload["job_id"]}, timeout=5.0)

# ==========================================
# 4. API 엔드포인트
# ==========================================
@app.get("/")
def read_root():
    return {"message": "Welcome to AI Analysis Server (Orchestrator Edition)"}

@app.post("/api/v1/analyze", status_code=status.HTTP_202_ACCEPTED)
async def trigger_analysis(request: AnalysisTriggerRequest, background_tasks: BackgroundTasks, token: str = Depends(verify_api_token)):
    background_tasks.add_task(process_audio_and_callback, job_id=request.job_id, user_id=request.user_id, file_path=request.file_path, callback_url=request.callback_url)
    return {"message": "Analysis started in background."}

@app.post("/api/v1/fast-chat", status_code=status.HTTP_202_ACCEPTED)
async def trigger_fast_chat(request: FastChatCallbackRequest, background_tasks: BackgroundTasks, token: str = Depends(verify_api_token)):
    background_tasks.add_task(process_fast_chat_and_callback, payload=request.dict())
    return {"message": "Fast chat started in background."}

#  엣지 라우팅
@app.post("/api/v1/edge/route", summary="Edge Device Real-time Routing & RAG Orchestration")
async def process_edge_routing(request: EdgeRouteRequest):
    raw_text = request.text
    user_id = request.user_id # 라즈베리 파이로부터 넘어온 유저 식별자
    
    print(f"📥 [Edge Request] 라즈베리 파이로부터 발화 수신: '{raw_text}'")

    routing_prompt = """
당신은 반려 로봇 '기억정원'의 라우터입니다. 어르신의 대화를 분석하여 정확히 JSON으로만 응답하세요.
1. intent 구분: RAG_REQ (과거 기억 탐색 필요) / SIMPLE_CHAT (가벼운 스몰톡)
2. local_reply: SIMPLE_CHAT일 때만 다정한 복지사 말투(해요체)로 작성. RAG_REQ일 때는 반드시 빈 문자열("").
3. privacy_flag: '비밀', '지워' 등이 포함되면 true. safe_text에 '[발화 정보 보호됨]' 입력.
[JSON 형식]
{"intent": "RAG_REQ" | "SIMPLE_CHAT", "privacy_flag": true/false, "safe_text": "원문/요약", "local_action": null, "local_reply": "스몰톡 답변"}
"""
    try:
        response = await client.chat.completions.create(
            model=LIGHT_LLM_MODEL,
            messages=[{"role": "system", "content": routing_prompt}, {"role": "user", "content": raw_text}],
            temperature=0.0, response_format={"type": "json_object"}, timeout=5.0
        )
        routing_data = json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"❌ [1차 라우팅 실패]: {e}")
        return {"intent": "SIMPLE_CHAT", "privacy_flag": False, "safe_text": raw_text, "local_action": None, "local_reply": "네 어르신, 제가 귀 기울여 듣고 있어요."}

    # RAG 분기 감지 시 백엔드 DB 검색 후 데이터 교직
    if routing_data.get("intent") == "RAG_REQ":
        print("☁️ [Orchestration] RAG 분기 감지. 백엔드 지식망 동기 검색 시작...")
        query_vector = await get_embedding(raw_text)
        
        past_memories = await fetch_memories_from_backend(query_vector, user_id)
        
        rag_synthesis_prompt = f"""
당신은 경력 10년 차의 따뜻하고 숙련된 노인 전문 복지사 '기억정원'입니다.
제공된 [과거 기억 정보]를 바탕으로, 어르신의 질문에 친절하고 명확하게 답변해 주세요.

[과거 기억 정보]
{past_memories if past_memories else "관련된 과거 기록이 데이터베이스에 존재하지 않습니다."}

- 기억 정보에 기반하여 어르신이 안심하실 수 있도록 다정한 해요체로 대답하세요.
- 답변은 핵심만 짚어 이해하기 쉽게 2문장 내외로 간결하게 작성하세요.
"""
        try:
            synthesis_response = await client.chat.completions.create(
                model=LIGHT_LLM_MODEL,
                messages=[{"role": "system", "content": rag_synthesis_prompt}, {"role": "user", "content": raw_text}],
                temperature=0.3, timeout=6.0
            )
            routing_data["local_reply"] = synthesis_response.choices[0].message.content
        except:
            routing_data["local_reply"] = "어르신, 제가 기억 상자를 열심히 뒤지고 있어요. 잠시 후 다시 한 번 말씀해 주시겠어요?"

    return routing_data