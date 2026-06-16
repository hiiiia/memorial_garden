from fastapi import FastAPI, BackgroundTasks, HTTPException, status, Header, Depends
from pydantic import BaseModel
import httpx
import os
import json
import asyncio
import subprocess
import urllib.parse
import numpy as np

# 1. openai-whisper 대신 faster-whisper 임포트
#import whisper
from faster_whisper import WhisperModel

from openai import OpenAI
from app.config import settings
from app.utils.backup import save_failed_callback_to_local

app = FastAPI()

# ==========================================
# 1. 환경 변수 및 Gemini 클라이언트 설정
# ==========================================
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
AI_SECRET_TOKEN = os.getenv("AI_SECRET_TOKEN", "my_super_secret_ai_token")
HF_TOKEN = os.getenv("HF_TOKEN", "default-token")

client = OpenAI(
    base_url="http://codu.ddns.net:11434/v1",
    api_key="ollama"
)
LLM_MODEL = "gemma4:12b"
EMBEDDING_MODEL = "nomic-embed-text"

# print("🎙️ Whisper STT 모델 로딩 중... (서버 시작 시 1회만 실행)")
# whisper_model = whisper.load_model("base")
print("🎙️ Faster-Whisper STT 모델 로딩 중...")
# int8(8비트) 양자화 옵션 적용
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

def verify_api_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized. Missing token.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token != settings.AI_SECRET_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized. Invalid token.")
    return token

# ==========================================
# 에러 콜백 전송 함수
# ==========================================
async def send_failed_callback(callback_url: str, user_id: str, headers: dict, error_code: str, error_msg: str, job_id: str):
    """
    분석 또는 이미지 생성 단계에서 실패했을 때 백엔드로 FAILED 상태와 에러 코드를 전송합니다.
    이 전송마저 실패하면 로컬 디스크에 JSON을 저장합니다.
    """
    error_callback_body = {
        "user_id": user_id,
        "status": "FAILED",
        "error_code": error_code,      # 추가된 에러 코드
        "error_message": error_msg,    # 추가된 에러 메시지
        "analysis_data": {
            "risk_score": 0.0,
            "primary_emotion": "neutral",
            "llm_summary": f"[{error_code}] {error_msg}",
            "reply_text": "죄송합니다. 서버 문제로 분석을 완료하지 못했습니다. 잠시 후 다시 시도해 주세요.",
            "stt_text": "",
            "image_url": ""            # 백엔드 명세에 맞춤
        }
    }

    try:
        async with httpx.AsyncClient() as http_client:
            print(f"\n[AI Error Handler] 백엔드로 FAILED 콜백 전송 중... ({error_code})")
            res = await http_client.post(callback_url, json=error_callback_body, headers=headers)
            res.raise_for_status()
            print(f"[AI Error Handler] FAILED 콜백 전송 완료. 상태코드: {res.status_code}")
            
    except Exception as callback_err:
        print(f"\n[AI Fatal Error] 백엔드로 FAILED 콜백 전송 실패: {str(callback_err)}")
        print("[AI Recovery] FAILED 데이터를 로컬 디스크에 백업합니다...")
        # 백엔드 서버가 죽어있는 경우 로컬에 저장
        save_failed_callback_to_local(
            job_id=job_id,
            user_id=user_id,
            payload=error_callback_body,
            error_reason=f"FAILED 콜백 송신 실패: {str(callback_err)}"
        )

# ==========================================
# [STT 추출] FFmpeg 제어 로직
# ==========================================
def extract_audio_with_ffmpeg(file_path: str, target_sr: int = 16000) -> np.ndarray:
    print(f"\n[FFmpeg] 🎬 오디오 추출 시작: {file_path}")
    
    command = [
        "ffmpeg",               # apt-get으로 설치했으므로 글로벌 명령어 사용
        "-i", file_path,
        "-f", "f32le",
        "-ac", "1",
        "-ar", str(target_sr),
        "-loglevel", "quiet",
        "-"
    ]
    
    try:
        out, _ = subprocess.Popen(command, stdout=subprocess.PIPE).communicate()
    except FileNotFoundError:
        raise RuntimeError("[FFmpeg Error] 컨테이너 내부에 ffmpeg가 설치되어 있지 않습니다.")
    except Exception as e:
        raise RuntimeError(f"[FFmpeg Error] 실행 중 예외 발생: {e}")
        
    return np.frombuffer(out, np.float32).flatten()

# ==========================================
# [무료 이미지 생성] Pollinations AI (재시도 로직 포함)
# ==========================================
# async def generate_diary_image(image_prompt: str, job_id: str, max_retries: int = 3, base_delay: int = 5) -> str:
#     if not image_prompt:
#         return ""

#     print("\n[AI Image] 🎨 Pollinations API로 그림일기 생성 중 (워터마크 허용)...")
    
#     enhanced_prompt = f"{image_prompt}, watercolor style, warm colors, fairy tale illustration"
#     encoded_prompt = urllib.parse.quote(enhanced_prompt)
    
#     # 🌟 핵심: nologo=true 옵션을 빼면 다시 무료로 작동합니다!
#     api_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=512&height=512"

#     save_dir = "/app/uploads/diary_images"
#     os.makedirs(save_dir, exist_ok=True)
#     file_name = f"diary_{job_id}.png"
#     save_path = os.path.join(save_dir, file_name)

#     for attempt in range(1, max_retries + 1):
#         try:
#             async with httpx.AsyncClient() as http_client:
#                 response = await http_client.get(api_url, timeout=60.0)
#                 response.raise_for_status()

#                 with open(save_path, "wb") as f:
#                     f.write(response.content)

#             image_url = f"http://localhost:8000/static/diary_images/{file_name}"
#             print(f"[AI Image] ✅ 그림일기 저장 완료: {save_path}")
#             return image_url

#         except Exception as e:
#             print(f"[AI Image Error] 이미지 다운로드 실패 (시도 {attempt}): {str(e)}")
#             if attempt < max_retries:
#                 await asyncio.sleep(base_delay * attempt)
#             else:
#                 return ""


async def generate_diary_image(image_prompt: str, job_id: str, max_retries: int = 3, base_delay: int = 5) -> str:
    if not image_prompt:
        return ""

    print("\n[AI Image] 🚧 외부 AI 이미지 API 과금으로 인한 디버깅용 함수 실행. 테스트용 임시(Dummy) 이미지를 다운로드합니다...")
    
    # AI 이미지 대신, placehold.co 에서 제공하는 512x512 사이즈의 가짜 임시 이미지 활용
    dummy_url = "https://placehold.co/512x512/e2e8f0/475569.png?text=Picture+Diary+Test"
    
    save_dir = "/app/uploads/diary_images"
    os.makedirs(save_dir, exist_ok=True)
    file_name = f"diary_{job_id}.png"
    save_path = os.path.join(save_dir, file_name)

    try:
        async with httpx.AsyncClient() as http_client:
            # 봇 차단(WAF) 방화벽을 피하기 위해 일반 크롬 브라우저인 척 위장
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            
            response = await http_client.get(dummy_url, headers=headers, timeout=30.0)
            response.raise_for_status()

            with open(save_path, "wb") as f:
                f.write(response.content)

        image_url = f"http://localhost:8000/static/diary_images/{file_name}"
        print(f"[AI Image] ✅ 테스트용 임시 이미지 저장 완료 (콜백 전송 진행): {save_path}")
        return image_url

    except Exception as e:
        print(f"[AI Image Error] 더미 이미지조차 다운로드 실패: {str(e)}")
        # 최악의 경우 파일 생성조차 실패하면 백엔드 에러를 막기 위해 빈 문자열 반환
        return ""

# ==========================================
# 3. 메인 분석 파이프라인
# ==========================================
async def process_audio_and_callback(job_id: str, user_id: str, file_path: str, callback_url: str):
    if not os.path.exists(file_path):
        print(f"[AI Error] 파일을 찾을 수 없습니다: {file_path}")
        return

    max_retries = 3
    base_delay = 5 

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.AI_SECRET_TOKEN}"
    }

    analysis_result = None

    print(f"\n[AI] === {LLM_MODEL} 파이프라인 시작 ===")
    
    # ---------------------------------------------------------
    # [Phase 0] FFmpeg + Whisper STT & RAG 검색
    # ---------------------------------------------------------
    
    print("\n[AI] 🔍 과거 기억 검색을 위한 사전 STT 추출 시작...")
    
    quick_stt_text = ""
    past_memories = []
    
    try:
        audio_array = extract_audio_with_ffmpeg(file_path)
        
        #result = whisper_model.transcribe(audio_array)
        #quick_stt_text = result.get("text", "").strip()
        # ================================================
        # Faster-Whisper는 텍스트 덩어리(segments)를 순차적으로 뱉어내므로 하나로 합쳐줍니다.
        segments, info = whisper_model.transcribe(audio_array, beam_size=5, language="ko")
        quick_stt_text = " ".join([segment.text for segment in segments]).strip()
        
        print(f"[AI STT 결과] {quick_stt_text}")

        if quick_stt_text:
            embed_res = client.embeddings.create(model=EMBEDDING_MODEL, input=quick_stt_text)
            query_vector = embed_res.data[0].embedding
            
            print("[AI] 🔍 백엔드 DB에서 관련된 과거 기억 조회 중...")
            
            async with httpx.AsyncClient() as http_client:
                search_res = await http_client.post(
                    f"{BACKEND_URL}/api/v1/memory/search/{user_id}",
                    json={"query_vector": query_vector, "limit": 3},
                    headers=headers
                )
                if search_res.status_code == 200:
                    past_memories = search_res.json().get("memories", [])
                    print(f"[AI] ✅ 관련된 과거 기억 {len(past_memories)}개 발견!")
    except Exception as e:
        print(f"[AI Warning] STT/RAG 에러 (기억 없이 진행): {e}")

    # 찾아온 과거 기억을 하나의 문자열로 포매팅
    memory_context = "\n- ".join(past_memories) if past_memories else "이전 대화와 관련된 특별한 기억이 없습니다."
    
    # ---------------------------------------------------------
    # [Phase 1] LLM 텍스트 분석(과거 기억 주입)
    # ---------------------------------------------------------
    for attempt in range(1, max_retries + 1):
        try:
            print(f"\n[AI] === 텍스트 분석 시도 횟수 : {attempt}/{max_retries} ===")
            
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
            
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant. Output only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            try:
                analysis_result = json.loads(response.choices[0].message.content)
            except json.JSONDecodeError as json_err:
                raise json_err

            print("[AI] ✅ 분석 성공!")
            print(json.dumps(analysis_result, indent=2, ensure_ascii=False))
            break

        except Exception as e:
            print(f"[AI Warning] 분석 실패: {str(e)}")
            if attempt < max_retries:
                await asyncio.sleep(base_delay * attempt)
            else:
                print(f"\n[AI Critical Error] AI 분석 최대 재시도 초과.")
                # LLM 분석 실패 에러 코드 전송
                await send_failed_callback(callback_url, user_id, headers, "LLM_ANALYSIS_FAILED", "텍스트 분석 응답 오류", job_id)
                return

    # =========================================================
    # [Phase 1.5] 분석된 요약본을 벡터로 변환 (장기 기억 DB 저장용)
    # =========================================================
    vector_embedding = None
    llm_summary = analysis_result.get("llm_summary", "")
    
    if llm_summary:
        try:
            print("\n[AI] 🧠 요약 텍스트를 벡터로 변환 중 (장기 기억 저장용)...")
            save_embed = client.embeddings.create(model=EMBEDDING_MODEL, input=llm_summary)
            vector_embedding = save_embed.embeddings[0].values
            print("[AI] ✅ 저장용 벡터 변환 완료!")
        except Exception as e:
            vector_embedding = [0.0] * 3072 # None 대신 0.0 배열 초기화
            print(f"[AI Warning] 저장용 벡터 변환 실패: {e}")


    # ---------------------------------------------------------
    # [Phase 2] 그림일기 이미지 생성
    # ---------------------------------------------------------
    image_prompt = analysis_result.get("image_prompt", "")
    image_url = ""

    if image_prompt:
        
        print("[AI] : 그림일기 이미지 생성 중...")
        
        image_url = image_url = await generate_diary_image(image_prompt, job_id, max_retries, base_delay)
        
        # 이미지를 생성해야 하는데 결과가 빈 문자열(실패)로 돌아온 경우
        if not image_url:
            print(f"\n[AI Critical Error] 이미지 생성 실패.")
            await send_failed_callback(callback_url, user_id, headers, "IMAGE_GENERATION_FAILED", "그림일기 이미지 생성 시간 초과 및 오류", job_id)
            return # 이미지 실패 시 프로세스 종료

    # ---------------------------------------------------------
    # [Phase 3] 백엔드 성공 콜백 전송 및 로컬 백업
    # ---------------------------------------------------------
    risk_score = float(analysis_result.get("risk_score", 0.0))

    # 백엔드 명세에 맞춘 페이로드
    callback_body = {
        "user_id": user_id,
        "status": "COMPLETED",
        "error_code": None,
        "error_message": None,
        "analysis_data": {
            "risk_score": risk_score,
            "primary_emotion": analysis_result.get("primary_emotion", "neutral"),
            "llm_summary": analysis_result.get("llm_summary", ""),
            "reply_text": analysis_result.get("reply_text", "오늘의 이야기를 소중히 기록해 두었습니다."),
            "stt_text": analysis_result.get("stt_text", ""),
            "image_url": image_url, 
            "depression_score": float(analysis_result.get("depression_score", 0.0)),
            "cognitive_decline_score": float(analysis_result.get("cognitive_decline_score", 0.0)),
            "care_level": analysis_result.get("care_level", "NORMAL"),
            "vector_embedding": vector_embedding # PostgreSQL에 저장할 기억 메모리
        }
    }

    for attempt in range(1, max_retries + 1):
        try:
            print(f"\n[AI] 백엔드로 COMPLETED 콜백 송신 중... (시도: {attempt}/{max_retries})")
            async with httpx.AsyncClient() as http_client:
                res = await http_client.post(callback_url, json=callback_body, headers=headers)
                
                
                if res.status_code == 422:
                    print(f"\n[AI 422 Error Detail] 백엔드가 거절한 이유:\n{res.text}")
                    print(f"[AI 보낸 데이터 확인] {callback_body}") # 우리가 뭘 보냈는지도 확인
                
                
                res.raise_for_status()
                print(f"[AI] ✅ 백엔드 전송 완료! 상태코드: {res.status_code}")
            break

        except Exception as e:
            print(f"[AI Warning] 백엔드 콜백 전송 실패: {str(e)}")
            if attempt < max_retries:
                await asyncio.sleep(base_delay * attempt)
            else:
                print(f"\n[AI Critical Error] COMPLETED 콜백 전송 최대 재시도 초과.")
                print("[AI Recovery] 성공한 분석 데이터의 유실 방지를 위해 로컬 저장을 시도합니다...")
                
                # 최종 성공한 데이터지만, 네트워크 문제로 백엔드 전송이 실패했을 경우 로컬 디스크에 백업
                save_failed_callback_to_local(
                    job_id=job_id,
                    user_id=user_id,
                    payload=callback_body,
                    error_reason="COMPLETED 콜백 백엔드 전송 실패 (서버 다운 또는 네트워크 오류)"
                )


# ==========================================
# 3. 빠른 분석 파이프라인
# ==========================================
async def process_fast_chat_and_callback(payload: dict):
    prompt = f"""
    당신은 어르신을 보살피는 친절하고 따뜻한 손주/말벗입니다.
    아래 과거 기억을 참고하여 어르신의 말씀에 1~2문장으로 짧고 다정하게 대답해 주세요.
    
    [과거 기억]
    {payload['memory_context']}
    
    [어르신 말씀]
    {payload['user_text']}
    """
    
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "친절한 AI 말벗입니다. JSON이 아닌 일반 텍스트로만 대답하세요."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        ai_answer = response.choices[0].message.content.strip()
        print(f"[AI] ⚡ 빠른 답변 생성 완료. 콜백 전송 시작 (Job: {payload['job_id']})")

        # 2. 분석 완료 시 백엔드로 성공 콜백 전송
        async with httpx.AsyncClient() as http_client:
            await http_client.post(
                payload["callback_url"],
                json={"status": "COMPLETED", "reply_text": ai_answer, "job_id": payload["job_id"]}
            )
            
    except Exception as e:
        print(f"[AI Error] 빠른 답변 생성 실패: {e}")
        # 실패 시 에러 콜백 전송
        async with httpx.AsyncClient() as http_client:
            await http_client.post(
                payload["callback_url"],
                json={"status": "FAILED", "reply_text": "제가 잠시 딴생각을 하느라 못 들었어요.", "job_id": payload["job_id"]}
            )


@app.get("/")
def read_root():
    return {"message": "Welcome to AI Analysis Server (Gemini)"}

@app.post("/api/v1/analyze", status_code=status.HTTP_202_ACCEPTED)
async def trigger_analysis(
    request: AnalysisTriggerRequest,
    background_tasks: BackgroundTasks,
    token: str = Depends(verify_api_token)
):
    background_tasks.add_task(
        process_audio_and_callback,
        job_id=request.job_id,
        user_id=request.user_id,
        file_path=request.file_path,
        callback_url=request.callback_url
    )
    return {"message": "Analysis started in background."}


@app.post("/api/v1/fast-chat", status_code=status.HTTP_202_ACCEPTED)
async def trigger_fast_chat(request: FastChatCallbackRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_fast_chat_and_callback, request.dict())
    return {"message": "Fast chat started in background."}