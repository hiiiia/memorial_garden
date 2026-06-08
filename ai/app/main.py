from fastapi import FastAPI, BackgroundTasks, HTTPException, status, Header, Depends
from pydantic import BaseModel
import httpx
import os
import json
import asyncio

from google import genai
from google.genai import types

from app.config import settings
from app.utils.backup import save_failed_callback_to_local
import asyncio

app = FastAPI()

# ==========================================
# 1. 환경 변수 및 Gemini 클라이언트 설정
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
AI_SECRET_TOKEN = os.getenv("AI_SECRET_TOKEN", "my_super_secret_ai_token")

client = genai.Client(api_key=settings.GEMINI_API_KEY)

# ==========================================
# 2. 데이터 스키마 및 보안 의존성 정의
# ==========================================
class AnalysisTriggerRequest(BaseModel):
    job_id: str
    user_id: str
    file_path: str  
    callback_url: str 
    
# 토큰 검증 함수
def verify_api_token(authorization: str = Header(None)):
    """
    들어오는 요청의 Header에서 Authorization 토큰을 검사합니다.
    """
    
    print(f"[보안 검사] 백엔드가 보낸 헤더: {authorization}")
    print(f"[보안 검사] AI 서버가 아는 토큰: {AI_SECRET_TOKEN}")
    
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized. Missing token.")
    
    scheme, _, token = authorization.partition(" ")
    
    # settings.AI_SECRET_TOKEN 으로 비교
    if scheme.lower() != "bearer" or token != settings.AI_SECRET_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized. Invalid token.")
    return token

# FAILED 콜백 코드
async def send_failed_callback(callback_url: str, user_id: str, headers: dict):
    error_callback_body = {
        "user_id": user_id,
        "status": "FAILED",
        "analysis_data": {
            "risk_score": 0.0,
            "primary_emotion": "neutral",
            "llm_summary": "서버 과부하 또는 AI 통신 에러로 분석을 완료하지 못했습니다."
        }
    }
    try:
        async with httpx.AsyncClient() as http_client:
            print(f"\n[AI Error Handler] 백엔드로 FAILED 콜백 전송 중...")
            res = await http_client.post(callback_url, json=error_callback_body, headers=headers)
            print(f"[AI Error Handler] FAILED 콜백 전송 완료. 상태코드: {res.status_code}")
    except Exception as callback_err:
        print(f"[AI Fatal Error] 백엔드로 FAILED 콜백마저 실패: {str(callback_err)}")


# ==========================================
# 3. 핵심 로직: Gemini 분석 및 백엔드 콜백 전송 (FAILED 처리 추가)
# ==========================================
async def process_audio_and_callback(job_id: str, user_id: str, file_path: str, callback_url: str):
    if not os.path.exists(file_path):
        print(f"[AI Error] 파일을 찾을 수 없습니다: {file_path}")
        return

    max_retries = 3
    base_delay = 5  # 기본 대기 시간(초)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.AI_SECRET_TOKEN}"
    }

    analysis_result = None
    print(f"\n[AI] === Gemini 분석 작업 시작===")
    print(f"[AI] 오디오 업로드 시작: {file_path}")
    
    try:
        # 1. 파일 업로드
        audio_file = client.files.upload(file=file_path)
    except Exception as upload_err:
        print(f"[AI Fatal Error] 파일 업로드 자체 실패: {upload_err}")
        await send_failed_callback(callback_url, user_id, headers)
        return
    
    # ---------------------------------------------------------
    # [Phase 1] Gemini 분석 (재시도 로직 독립)
    # ---------------------------------------------------------
    for attempt in range(1, max_retries + 1):
        try:
            print(f"\n[AI] === 분석 시도 횟수 : {attempt}/{max_retries}) ===")
            
            # 모델 리스트 출력 코드
            # print("\n[AI] === 내 API 키로 사용 가능한 모델 목록 ===")
            # try:
            #     for m in client.models.list():
            #         print(f" - {m.name}")
            # except Exception as list_err:
            #     print(f"[AI] 모델 목록 불러오기 실패: {list_err}")
            # print("=============================================\n")
            
            prompt = """
                당신은 노인 회상치료(Reminiscence Therapy) 전문가이자
                정서 케어 AI입니다.

                업로드된 음성 파일을 분석하여 사용자의 심리 상태와 대화 내용을 평가하세요.

                [분석 목표]

                1. 현재 감정 상태 분석
                2. 우울감, 고립감, 자살 위험 징후 분석
                3. 인지 저하 또는 기억력 저하 징후 분석
                4. 사용자가 언급한 과거 기억 및 추억 요약
                5. 회상치료를 위한 후속 질문 생성
                6. 라이프로그(오늘의 기억 일기) 생성
                7. 사용자에게 공감적인 답변 생성

                반드시 아래 JSON 형식으로만 응답하세요.

                {
                "risk_score": 0.0,
                "depression_score": 0.0,
                "isolation_score": 0.0,
                "cognitive_decline_score": 0.0,

                "primary_emotion": "neutral",

                "llm_summary": "",

                "memory_topics": [],

                "memory_questions": [],

                "life_log": "",

                "care_level": "NORMAL",

                "reply_text": ""
                }

                [점수 규칙]

                - 모든 score는 0.0 ~ 1.0 범위
                - 위험 징후가 없으면 0에 가깝게 평가
                - 위험 징후가 명확할수록 1에 가깝게 평가

                [care_level 규칙]

                NORMAL:
                일반적인 상태

                WATCH:
                관찰 필요

                WARNING:
                상담 또는 보호자 관심 필요

                EMERGENCY:
                즉각적인 보호자 개입 필요

                [memory_topics 규칙]

                - 사용자가 과거 기억이나 추억을 언급한 경우에만 작성
                - 관련 내용이 없으면 빈 배열 [] 반환

                [memory_questions 규칙]

                - 회상 주제가 존재할 때만 생성
                - 반드시 사용자의 발화 내용과 관련된 질문 생성
                - 회상 주제가 없으면 빈 배열 [] 반환
                - 최대 3개 생성

                [life_log 규칙]

                - 사용자의 대화 내용을 바탕으로 작성
                - 3~5문장 정도의 짧은 일기 형식
                - 실제 언급하지 않은 사실은 상상해서 추가하지 말 것

                [reply_text 규칙]

                - 따뜻하고 공감적인 돌봄 동반자의 말투
                - 자연스러운 존댓말 사용
                - 과도한 애교 금지
                - "~용", "~여", "~헤헤", "~꼬옥", ">_<" 사용 금지
                - 이모티콘 사용 금지
                - 차분하고 안정감 있는 표현 사용
                - 사용자의 이야기에 공감할 것
                - 대화를 자연스럽게 이어갈 질문 1개 포함

                좋은 예:
                "그러셨군요. 그 기억이 아직도 많이 남아 있으신 것 같습니다. 그때 가장 기억에 남는 일은 무엇이었나요?"

                나쁜 예:
                "어머~ 그러셨구나용~ 헤헤 >_<"

                [중요]

                - 음성이 단순 테스트(예: "테스트", "하나 둘 셋")인 경우
                - risk_score는 0에 가깝게 평가
                - memory_topics는 []
                - memory_questions는 []
                - life_log는 테스트 내용을 간단히 기록
                - 과도한 해석 금지

                JSON 외의 문장은 절대 출력하지 마세요.
                """

            print("[AI] Gemini 분석 요청 중...")
            
            # # 2. 분석 요청
            # response = client.models.generate_content(
            #     #model='gemini-flash-latest',
            #     model = 'gemini-3-flash-preview',
            #     contents=[audio_file, prompt],
            #     config=types.GenerateContentConfig(
            #         response_mime_type="application/json"
            #     )
            # )
            #     ## 2026/05/29v.
            #     # ai-1  | [AI] === 내 API 키로 사용 가능한 모델 목록 ===
            #     # ai-1  |  - models/gemini-2.5-flash
            #     # ai-1  |  - models/gemini-2.5-pro
            #     # ai-1  |  - models/gemini-2.0-flash
            #     # ai-1  |  - models/gemini-2.0-flash-001
            #     # ai-1  |  - models/gemini-2.0-flash-lite-001
            #     # ai-1  |  - models/gemini-2.0-flash-lite
            #     # ai-1  |  - models/gemini-2.5-flash-preview-tts
            #     # ai-1  |  - models/gemini-2.5-pro-preview-tts
            #     # ai-1  |  - models/gemma-4-26b-a4b-it
            #     # ai-1  |  - models/gemma-4-31b-it
            #     # ai-1  |  - models/gemini-flash-latest
            #     # ai-1  |  - models/gemini-flash-lite-latest
            #     # ai-1  |  - models/gemini-pro-latest
            #     # ai-1  |  - models/gemini-2.5-flash-lite
            #     # ai-1  |  - models/gemini-2.5-flash-image
            #     # ai-1  |  - models/gemini-3-pro-preview
            #     # ai-1  |  - models/gemini-3-flash-preview
            #     # ai-1  |  - models/gemini-3.1-pro-preview
            #     # ai-1  |  - models/gemini-3.1-pro-preview-customtools
            #     # ai-1  |  - models/gemini-3.1-flash-lite-preview
            #     # ai-1  |  - models/gemini-3.1-flash-lite
            #     # ai-1  |  - models/gemini-3-pro-image-preview
            #     # ai-1  |  - models/gemini-3-pro-image
            #     # ai-1  |  - models/nano-banana-pro-preview
            #     # ai-1  |  - models/gemini-3.1-flash-image-preview
            #     # ai-1  |  - models/gemini-3.1-flash-image
            #     # ai-1  |  - models/gemini-3.5-flash
            #     # ai-1  |  - models/lyria-3-clip-preview
            #     # ai-1  |  - models/lyria-3-pro-preview
            #     # ai-1  |  - models/gemini-3.1-flash-tts-preview
            #     # ai-1  |  - models/gemini-robotics-er-1.5-preview
            #     # ai-1  |  - models/gemini-robotics-er-1.6-preview
            #     # ai-1  |  - models/gemini-2.5-computer-use-preview-10-2025
            #     # ai-1  |  - models/antigravity-preview-05-2026
            #     # ai-1  |  - models/deep-research-max-preview-04-2026
            #     # ai-1  |  - models/deep-research-preview-04-2026
            #     # ai-1  |  - models/deep-research-pro-preview-12-2025
            #     # ai-1  |  - models/gemini-embedding-001
            #     # ai-1  |  - models/gemini-embedding-2-preview
            #     # ai-1  |  - models/gemini-embedding-2
            #     # ai-1  |  - models/aqa
            #     # ai-1  |  - models/imagen-4.0-generate-001
            #     # ai-1  |  - models/imagen-4.0-ultra-generate-001
            #     # ai-1  |  - models/imagen-4.0-fast-generate-001
            #     # ai-1  |  - models/veo-2.0-generate-001
            #     # ai-1  |  - models/veo-3.0-generate-001
            #     # ai-1  |  - models/veo-3.0-fast-generate-001
            #     # ai-1  |  - models/veo-3.1-generate-preview
            #     # ai-1  |  - models/veo-3.1-fast-generate-preview
            #     # ai-1  |  - models/veo-3.1-lite-generate-preview
            #     # ai-1  |  - models/gemini-2.5-flash-native-audio-latest
            #     # ai-1  |  - models/gemini-2.5-flash-native-audio-preview-09-2025
            #     # ai-1  |  - models/gemini-2.5-flash-native-audio-preview-12-2025
            #     # ai-1  |  - models/gemini-3.1-flash-live-preview
            #     # ai-1  | =============================================
                
                
            # analysis_result = json.loads(response.text)
            # print(f"[AI] Gemini 분석 완료: {analysis_result}")
            
            
            analysis_result = { }
            # -----------------------------------------------------

            print("[AI] ✅ Gemini 분석 성공!")
            break  # 분석 성공 시 Phase 1 루프 탈출

        except Exception as e:
            print(f"[AI Warning] Gemini 분석 실패: {str(e)}")
            if attempt < max_retries:
                wait_time = base_delay * attempt
                print(f"[AI Retry] {wait_time}초 후 분석을 다시 시도합니다...\n")
                await asyncio.sleep(wait_time)
            else:
                # break 없이 루프가 끝났다면 (최대 재시도 실패)
                print(f"\n[AI Critical Error] Gemini 분석 최대 재시도({max_retries}회) 초과.")
                await send_failed_callback(callback_url, user_id, headers)
                return # 분석에 실패했으므로 여기서 완전히 종료합니다.

    # ---------------------------------------------------------
    # [Phase 2] 백엔드 콜백 전송 (재시도 로직 독립)
    # Phase 1을 무사히 통과한 경우에만 실행됩니다.
    # ---------------------------------------------------------
    callback_body = {
        "user_id": user_id,
        "status": "COMPLETED",
        "analysis_data": {
            "risk_score": float(analysis_result.get("risk_score", 0.0)),
            "primary_emotion": analysis_result.get("primary_emotion", "neutral"),
            "llm_summary": analysis_result.get("llm_summary", ""),
            "stt_text" : analysis_result.get("stt_text", ""),
            "reply_text": analysis_result.get("reply_text", "제가 항상 곁에서 듣고 있어요. 조금 더 쉬시는 건 어떨까요?")
        }
    }

    for attempt in range(1, max_retries + 1):
        try:
            print(f"\n[AI] 백엔드로 COMPLETED 콜백 송신 중... (시도: {attempt}/{max_retries})")
            async with httpx.AsyncClient() as http_client:
                res = await http_client.post(callback_url, json=callback_body, headers=headers)
                res.raise_for_status() 
                print(f"[AI] ✅ 백엔드 전송 완료! 상태코드: {res.status_code}")
            
            break # 전송 성공 시 Phase 2 루프 정상 탈출

        except Exception as e:
            print(f"[AI Warning] 백엔드 콜백 전송 실패: {str(e)}")
            if attempt < max_retries:
                wait_time = base_delay * attempt
                print(f"[AI Retry] {wait_time}초 후 콜백 송신을 다시 시도합니다...\n")
                await asyncio.sleep(wait_time)

    else:
        # Phase 2의 for 루프가 break 없이 모두 실패로 끝났을 때 실행됨
        print(f"\n[AI Critical Error] COMPLETED 콜백 전송 최대 재시도({max_retries}회) 초과.")
        
        # 개선 포인트: Phase 1에서 이미 사용 중인 헬퍼 함수를 호출하여 중복 코드 제거!
        try:
            print(f"[AI] 백엔드로 FAILED 콜백 송신을 시도합니다...")
            await send_failed_callback(callback_url, user_id, headers)
            print(f"[AI] ✅ FAILED 상태 백엔드 전송 완료!")
        except Exception as fallback_e:
            print(f"\n[AI Fatal Error] FAILED 콜백 전송마저 실패했습니다: {str(fallback_e)}")
            print(f"[AI Recovery] 데이터 유실 방지를 위해 로컬 저장을 시도합니다...")
            
            # 로컬 Json 저장 함수
            save_failed_callback_to_local(
                job_id=job_id,
                user_id=user_id,
                payload=callback_body,       # 원본 데이터
                error_reason=str(fallback_e) # 실패한 이유
            )
            


@app.get("/")
def read_root():
    return {"message": "Welcome to AI Analysis Server (Gemini)"}

# ==========================================
# 4. 백엔드가 호출할 트리거 엔드포인트
# ==========================================
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