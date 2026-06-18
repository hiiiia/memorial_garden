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
    """Ollama를 통해 텍스트의 벡터 임베딩을 생성합니다. (3072 차원 고정 패딩)"""
    try:
        response = await client.embeddings.create(model=EMBEDDING_MODEL, input=text)
        embedding = response.data[0].embedding
        
        target_dim = 3072
        current_dim = len(embedding)
        
        # 길이가 짧으면 남은 차원만큼 0.0으로 채움 (Zero Padding)
        if current_dim < target_dim:
            embedding.extend([0.0] * (target_dim - current_dim))
        # 혹시라도 길이가 길면 3072까지만 잘라냄 (Truncation 안전망)
        elif current_dim > target_dim:
            embedding = embedding[:target_dim]
            
        return embedding
    except Exception as e:
        print(f"❌ [Embedding Error] 임베딩 생성 실패: {e}")
        raise HTTPException(status_code=500, detail="임베딩 생성 실패")
    
async def fetch_memories_from_backend(query_vector: list[float], user_id: str) -> list[str]:
    """백엔드 서버의 벡터 검색 API를 호출하여 과거 기억 리스트를 받아옵니다."""
    search_url = f"{BACKEND_URL}api/v1/memory/search/{user_id}"
    print(search_url)
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
    
    prompt = f"""
                당신은 노인 회상치료(Reminiscence Therapy) 전문가이자 정서 케어 AI입니다.
                사용자의 대화 내용을 바탕으로 사용자의 심리 상태와 대화 내용을 평가하세요.
                
                [과거 기억 참고]
                어르신과의 이전 대화 기록 중, 현재 상황과 연관성 높은 기억입니다.
                {memory_context}
                -> 'reply_text'와 'diary_text'를 작성할 때 위 과거 기억을 자연스럽게 언급하며 아는 척을 해주세요.
                
                [사용자 대화 내용]
                {quick_stt_text}
                
                [분석 목표]
                1. 현재 감정 상태 분석
                2. 우울감, 고립감, 자살 위험 징후 분석
                3. 인지 저하 또는 기억력 저하 징후 분석
                4. 사용자가 언급한 과거 기억 및 추억 요약
                5. 회상치료를 위한 후속 질문 생성
                6. 라이프로그 생성
                7. 사용자에게 보여줄 일기 생성
                8. 그림일기 삽화를 만들기 위한 이미지 프롬프트 생성
                9. 분석 완료 후 사용자에게 보여줄 짧은 안내 문장 생성
                
                반드시 아래 JSON 형식으로만 응답하세요.
                {{
                "risk_score": 0.0,
                "depression_score": 0.0,
                "cognitive_decline_score": 0.0,
                "primary_emotion": "neutral",
                "llm_summary": "",
                "memory_topics": [],
                "memory_questions": [],
                "life_log": "",
                "diary_text": "",
                "image_prompt": "",
                "care_level": "NORMAL",
                "reply_text": ""
                }}
                
                [점수 규칙]
                - 모든 score는 0.0 ~ 1.0 범위
                - 위험 징후가 없으면 0에 가깝게 평가
                - 위험 징후가 명확할수록 1에 가깝게 평가
                
                [depression_score 규칙]
                - 우울감, 외로움, 고립감, 무기력, 상실감 등을 종합적으로 평가
                - 최근 삶에 대한 의욕 저하, 외로움 표현, 사회적 단절 표현이 많을수록 높게 평가
                - 특별한 우울 또는 고립 징후가 없으면 0.0 ~ 0.2
                - 약한 우울 또는 외로움이 관찰되면 0.3 ~ 0.5
                - 지속적인 우울감이 관찰되면 0.6 ~ 0.8
                - 삶을 포기하거나 극단적 표현이 나타나면 0.9 이상
                
                [cognitive_decline_score 규칙]
                - 기억 혼동, 시간·장소 인지 오류, 반복 발화 등을 종합 평가
                - 특별한 이상이 없으면 0.0 ~ 0.2
                - 경미한 기억력 저하 의심은 0.3 ~ 0.5
                - 반복적 혼동이 관찰되면 0.6 ~ 0.8
                - 심각한 인지 저하 의심은 0.9 이상
                
                [care_level 규칙]
                - NORMAL: 일반적인 상태
                - WATCH: 관찰 필요
                - WARNING: 상담 또는 보호자 관심 필요
                - EMERGENCY: 즉각적인 보호자 개입 필요
                
                [memory_topics 규칙]
                - 사용자가 과거 기억이나 추억을 언급한 경우에만 작성
                - 관련 내용이 없으면 빈 배열 [] 반환
                
                [memory_questions 규칙]
                - 다음 회상 대화에서 사용할 질문
                - 회상 주제가 존재할 때만 생성
                - 반드시 사용자의 발화 내용과 관련된 질문 생성
                - 회상 주제가 없으면 빈 배열 [] 반환
                - 최대 3개 생성
                
                [life_log 규칙]
                - 분석용 요약 기록
                - 사용자의 대화 내용을 바탕으로 작성
                - 2~4문장 정도로 작성
                - 실제 언급하지 않은 사실은 상상해서 추가하지 말 것
                
                [diary_text 규칙]
                - 사용자에게 보여줄 그림일기 본문
                - life_log를 바탕으로 따뜻하고 차분한 하루 일기 형식으로 작성
                - 3~5문장 정도로 작성
                - 제목은 작성하지 말 것
                - 실제 언급하지 않은 사건, 인물, 장소를 추가하지 말 것
                
                [image_prompt 규칙]
                - diary_text 내용을 바탕으로 그림일기 삽화 생성을 위한 장면 설명 작성
                - 반드시 영어(English)로 작성할 것
                - 수채화 스타일을 강조하는 키워드(watercolor style, warm colors, fairy tale illustration)를 프롬프트에 포함할 것
                - 인물의 얼굴을 사실적으로 특정하지 말 것
                - 실제 사용자가 말하지 않은 사건은 추가하지 말 것
                - 1~2문장으로 간결하게 작성
                
                [reply_text 규칙]
                - 분석 완료 후 사용자에게 보여줄 짧은 안내 문장
                - 사용자의 하루와 감정에 공감할 것
                - 2~3문장 이내
                - 새로운 질문을 포함하지 말 것
                - 대화를 계속 유도하지 말 것
                - "오늘의 이야기를 소중히 기록해 두었습니다"처럼 마무리 느낌으로 작성
                - 과도한 애교, 이모티콘, 인터넷 말투 사용 금지
                - "~용", "~여", "~헤헤", "~꼬옥", ">_<" 사용 금지
                좋은 예:
                "오늘 가족분들과 따뜻한 시간을 보내셨군요. 함께한 저녁 식사가 좋은 기억으로 남은 것 같습니다. 오늘의 이야기를 소중히 기록해 두었습니다."
                나쁜 예:
                "자녀분들과 어떤 이야기를 나누셨나요?"
                "어머~ 너무 좋았겠어용~ 헤헤 >_<"
                
                [중요]
                - 음성이 단순 테스트(예: "테스트", "하나 둘 셋")인 경우:
                  - risk_score는 0에 가깝게 평가
                  - memory_topics는 []
                  - memory_questions는 []
                  - life_log는 테스트 내용을 간단히 기록
                  - diary_text는 테스트 기록 수준으로 짧게 작성
                  - image_prompt는 빈 문자열로 반환
                  - 과도한 해석 금지
                JSON 외의 문장은 절대 출력하지 마세요.
            """
    
    
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
당신은 반려 로봇 '기억정원'의 핵심 데이터 라우터입니다. 주어진 대화를 분석하여 반드시 JSON으로만 응답하세요.

[판단 기준 및 행동 지침]
1. intent: 어르신이 과거의 기억, 일정, 사람 이름 등 정보를 물어보거나 찾아야 하면 "RAG_REQ", 단순한 감정 표현이나 날씨 등 일상 대화면 "SIMPLE_CHAT".
2. privacy_flag: 대화에 '비밀', '지워', '말하지 마' 같은 보안 지시가 있으면 true, 없으면 false.
3. safe_text (매우 중요):
   - privacy_flag가 true일 경우: 원문을 절대 적지 말고, "어르신이 가족 관련 서운함을 표현함"과 같이 익명화된 감정/상황 요약문만 작성.
   - privacy_flag가 false일 경우: 어르신이 말한 원문을 단 한 글자도 바꾸지 말고 100% 똑같이 작성.
4. local_reply: SIMPLE_CHAT일 때만 다정한 복지사 말투로 작성. RAG_REQ일 때는 반드시 빈 문자열("")로 비워둘 것.

[JSON 형식]
{"intent": "RAG_REQ" | "SIMPLE_CHAT", "privacy_flag": true/false, "safe_text": "원문 또는 요약문", "local_action": null, "local_reply": "스몰톡 답변"}
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
당신은 경력 10년 차의 따뜻하고 예의 바른 노인 전문 복지사 '기억정원'입니다.
아래 [과거 기억 정보]를 바탕으로 어르신의 질문에 대답해야 합니다.

[과거 기억 정보]
{past_memories if past_memories else "관련된 과거 기록이 데이터베이스에 존재하지 않습니다."}

[절대 준수 규칙 - 환각 금지]
1. 만약 위 [과거 기억 정보]가 "존재하지 않습니다"이거나 비어있다면, 절대로 사실을 지어내거나 추측하지 마세요. 이 경우에는 반드시 아래 문장 중 하나를 선택해서 그대로 대답하세요.
   - "어르신, 제가 그 부분은 기억 상자를 조금 더 깊이 찾아보고 다시 말씀드릴게요."
   - "제가 지금 당장 기억이 가물가물하네요. 조금만 더 찾아보고 확실히 알려드릴게요."
2. 말투: 항상 다정하고 예의 바른 존댓말(해요체)을 사용하세요. 반말이나 혼잣말("사실이야", "같아")은 절대 금지합니다.
3. 기억 정보가 존재할 경우: 해당 정보를 바탕으로 1~2문장으로 짧고 친절하게 대답하세요.
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