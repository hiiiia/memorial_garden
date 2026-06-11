from fastapi import FastAPI, BackgroundTasks, HTTPException, status, Header, Depends
from pydantic import BaseModel
import httpx
import os
import json
import asyncio

# from google import genai
# from google.genai import types

from openai import OpenAI

from app.config import settings
from app.utils.backup import save_failed_callback_to_local

app = FastAPI()

# ==========================================
# 1. 환경 변수 및 Gemini 클라이언트 설정
# ==========================================
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
AI_SECRET_TOKEN = os.getenv("AI_SECRET_TOKEN", "my_super_secret_ai_token")

client = OpenAI(
    base_url="http://codu.ddns.net:11434/v1",
    api_key="ollama"
)


# ==========================================
# 2. 데이터 스키마 및 보안 의존성 정의
# ==========================================

class AnalysisTriggerRequest(BaseModel):
    job_id: str
    user_id: str
    file_path: str
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
# 이미지 생성 함수 (재시도 로직 포함)
# ==========================================
async def generate_diary_image(image_prompt: str, job_id: str, max_retries: int = 3, base_delay: int = 5) -> str:
    if not image_prompt:
        return ""

    print("\n[AI Image] 그림일기 이미지 생성 시작")
    print(f"[AI Image] image_prompt: {image_prompt}")

    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash-image",
                contents=[image_prompt]
            )

            save_dir = "/app/uploads/diary_images"
            os.makedirs(save_dir, exist_ok=True)

            file_name = f"diary_{job_id}.png"
            save_path = os.path.join(save_dir, file_name)

            for part in response.parts:
                if part.inline_data is not None:
                    image = part.as_image()
                    image.save(save_path)
                    image_url = f"http://localhost:8000/static/diary_images/{file_name}"
                    print(f"[AI Image] ✅ 이미지 저장 완료: {save_path}")
                    return image_url

            raise ValueError("응답에 이미지 데이터가 없습니다.")

        except Exception as e:
            print(f"[AI Image Error] 이미지 생성 실패 (시도 {attempt}): {str(e)}")
            if attempt < max_retries:
                await asyncio.sleep(base_delay * attempt)
            else:
                print(f"[AI Image Critical Error] 그림일기 이미지 생성 최대 재시도({max_retries}회) 초과.")
                return "" # 실패 시 빈 문자열 반환


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

    print("\n[AI] === Gemini 분석 작업 시작 ===")
    
    try:
        audio_file = client.files.upload(file=file_path)
    except Exception as upload_err:
        print(f"[AI Fatal Error] 음성 파일 업로드 실패: {upload_err}")
        # 파일 업로드 에러 코드 전송
        await send_failed_callback(callback_url, user_id, headers, "UPLOAD_FAILED", str(upload_err), job_id)
        return
    
    # ---------------------------------------------------------
    # [Phase 0] STT 추출 및 RAG 과거 기억 검색
    # ---------------------------------------------------------
    print("\n[AI] 🔍 과거 기억 검색을 위한 사전 STT 추출 시작...")
    quick_stt_text = ""
    query_vector = []
    past_memories = []

    try:
        # 1. 메인 분석 전, 음성에서 텍스트만 빠르게 추출
        stt_res = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=[audio_file, "이 음성에서 들리는 사용자의 말을 있는 그대로 텍스트로만 적어주세요. 다른 설명은 절대 추가하지 마세요."]
        )
        quick_stt_text = stt_res.text.strip()
        print(f"[AI STT 추출] {quick_stt_text}")

        if quick_stt_text:
            # 2. 추출된 텍스트를 검색용 768차원 벡터로 변환
            embed_res = client.models.embed_content(
                model="gemini-embedding-2",
                contents=quick_stt_text
            )
            query_vector = embed_res.embeddings[0].values
            
            # 3. httpx를 이용해 백엔드에 비동기 검색 요청 (POST)
            print("[AI] 🔍 백엔드 DB에서 관련된 과거 기억 조회 중...")
            async with httpx.AsyncClient() as http_client:
                search_res = await http_client.post(
                    f"{BACKEND_URL}/api/v1/memory/{user_id}/search",
                    json={"query_vector": query_vector, "limit": 3},
                    headers=headers
                )
                if search_res.status_code == 200:
                    past_memories = search_res.json().get("memories", [])
                    print(f"[AI] ✅ 관련된 과거 기억 {len(past_memories)}개 발견!")
                else:
                    print(f"[AI Warning] 백엔드 검색 API 에러: {search_res.status_code}")

    except Exception as e:
        print(f"[AI Warning] RAG 검색 파이프라인 에러 (기억 없이 진행): {e}")

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
                업로드된 음성 파일을 분석하여 사용자의 심리 상태와 대화 내용을 평가하세요.
                
                [과거 기억 참고]
                어르신과의 이전 대화 기록 중, 현재 상황과 연관성 높은 기억입니다.
                {memory_context}
                -> 'reply_text'와 'diary_text'를 작성할 때 위 과거 기억을 자연스럽게 언급하며 아는 척을 해주세요.
                
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
                "stt_text": "",
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
                [stt_text 규칙]
                - 음성에서 인식한 사용자의 발화를 가능한 한 그대로 한국어 텍스트로 작성
                - 인식이 어렵다면 빈 문자열로 반환
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
                - 한국어로 작성
                - 따뜻한 수채화 스타일
                - 동화책 삽화 스타일
                - 인물의 얼굴을 사실적으로 특정하지 말 것
                - 실제 사용자가 말하지 않은 사건은 추가하지 말 것
                - 1~2문장으로 작성
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
            
            response = client.models.generate_content(
                model="gemini-3.5-flash",
                contents=[audio_file, prompt],
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            
            #     ## 2026/05/29v.
            #     # ai-1  | [AI] === 내 API 키로 사용 가능한 모델 목록 ===
            #     # ai-1  |  - models/gemini-2.5-flash
            #     # ai-1  |  - models/gemini-2.5-pro
            #     # ai-1  |  - models/gemini-2.0-flash
            #     # ai-1  |  - models/gemini-2.0-flash-001
            #     # ai-1  |  - models/gemini-2.0-flash-lite-001
            #     # ai-1  |  - models/gemini-2.0-flash-lite
            #     # ai-1  |  - models/gemini-2.5-flash-preview-tts
            #     # ai-1  |  - models/gemini-2.5-pro-preview-tts
            #     # ai-1  |  - models/gemma-4-26b-a4b-it
            #     # ai-1  |  - models/gemma-4-31b-it
            #     # ai-1  |  - models/gemini-flash-latest
            #     # ai-1  |  - models/gemini-flash-lite-latest
            #     # ai-1  |  - models/gemini-pro-latest
            #     # ai-1  |  - models/gemini-2.5-flash-lite
            #     # ai-1  |  - models/gemini-2.5-flash-image
            #     # ai-1  |  - models/gemini-3-pro-preview
            #     # ai-1  |  - models/gemini-3-flash-preview
            #     # ai-1  |  - models/gemini-3.1-pro-preview
            #     # ai-1  |  - models/gemini-3.1-pro-preview-customtools
            #     # ai-1  |  - models/gemini-3.1-flash-lite-preview
            #     # ai-1  |  - models/gemini-3.1-flash-lite
            #     # ai-1  |  - models/gemini-3-pro-image-preview
            #     # ai-1  |  - models/gemini-3-pro-image
            #     # ai-1  |  - models/nano-banana-pro-preview
            #     # ai-1  |  - models/gemini-3.1-flash-image-preview
            #     # ai-1  |  - models/gemini-3.1-flash-image
            #     # ai-1  |  - models/gemini-3.5-flash
            #     # ai-1  |  - models/lyria-3-clip-preview
            #     # ai-1  |  - models/lyria-3-pro-preview
            #     # ai-1  |  - models/gemini-3.1-flash-tts-preview
            #     # ai-1  |  - models/gemini-robotics-er-1.5-preview
            #     # ai-1  |  - models/gemini-robotics-er-1.6-preview
            #     # ai-1  |  - models/gemini-2.5-computer-use-preview-10-2025
            #     # ai-1  |  - models/antigravity-preview-05-2026
            #     # ai-1  |  - models/deep-research-max-preview-04-2026
            #     # ai-1  |  - models/deep-research-preview-04-2026
            #     # ai-1  |  - models/deep-research-pro-preview-12-2025
            #     # ai-1  |  - models/gemini-embedding-001
            #     # ai-1  |  - models/gemini-embedding-2-preview
            #     # ai-1  |  - models/gemini-embedding-2
            #     # ai-1  |  - models/aqa
            #     # ai-1  |  - models/imagen-4.0-generate-001
            #     # ai-1  |  - models/imagen-4.0-ultra-generate-001
            #     # ai-1  |  - models/imagen-4.0-fast-generate-001
            #     # ai-1  |  - models/veo-2.0-generate-001
            #     # ai-1  |  - models/veo-3.0-generate-001
            #     # ai-1  |  - models/veo-3.0-fast-generate-001
            #     # ai-1  |  - models/veo-3.1-generate-preview
            #     # ai-1  |  - models/veo-3.1-fast-generate-preview
            #     # ai-1  |  - models/veo-3.1-lite-generate-preview
            #     # ai-1  |  - models/gemini-2.5-flash-native-audio-latest
            #     # ai-1  |  - models/gemini-2.5-flash-native-audio-preview-09-2025
            #     # ai-1  |  - models/gemini-2.5-flash-native-audio-preview-12-2025
            #     # ai-1  |  - models/gemini-3.1-flash-live-preview
            #     # ai-1  | =============================================


            try:
                analysis_result = json.loads(response.text)
            except json.JSONDecodeError as json_err:
                raise json_err

            print("[AI] ✅ Gemini 분석 성공!")
            break

        except Exception as e:
            print(f"[AI Warning] Gemini 분석 실패: {str(e)}")
            if attempt < max_retries:
                await asyncio.sleep(base_delay * attempt)
            else:
                print(f"\n[AI Critical Error] Gemini 분석 최대 재시도 초과.")
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
            save_embed = client.models.embed_content(
                model="gemini-embedding-2",
                contents=llm_summary
            )
            vector_embedding = save_embed.embeddings[0].values
            print("[AI] ✅ 저장용 벡터 변환 완료!")
        except Exception as e:
            print(f"[AI Warning] 저장용 벡터 변환 실패: {e}")


    # ---------------------------------------------------------
    # [Phase 2] 그림일기 이미지 생성
    # ---------------------------------------------------------
    image_prompt = analysis_result.get("image_prompt", "")
    image_url = ""

    if image_prompt:
        image_url = await generate_diary_image(
            image_prompt=image_prompt,
            job_id=job_id,
            max_retries=max_retries,
            base_delay=base_delay
        )
        
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
            "vector_embedding": vector_embedding # PostgreSQL에 저장할 기억 메모리 / 768차원 배열
        }
    }

    for attempt in range(1, max_retries + 1):
        try:
            print(f"\n[AI] 백엔드로 COMPLETED 콜백 송신 중... (시도: {attempt}/{max_retries})")
            async with httpx.AsyncClient() as http_client:
                res = await http_client.post(callback_url, json=callback_body, headers=headers)
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