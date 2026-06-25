import os
import uuid
import json
import edge_tts
import aiohttp
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session
from core.config import settings
from db.database import SessionLocal
from db import models
from api.v1.ws.websocket_manager import device_ws_manager # 기존 웹소켓 매니저



# async def generate_tts_audio_open_ai(text: str, job_id: str) -> str:
#     """OpenAI TTS를 호출하여 음성 파일을 생성하고 경로를 반환합니다."""
    
#     # 저장할 파일명과 경로 세팅 (기존에 세팅하신 shared_uploads 폴더 활용)
#     file_name = f"reply_{job_id}.mp3"
#     save_path = os.path.join("shared_uploads", file_name)
#     static_url = f"http://localhost:8000/static/{file_name}" # 스피커가 접근할 URL
    
#     url = "https://api.openai.com/v1/audio/speech"
#     headers = {
#         "Authorization": f"Bearer {OPENAI_API_KEY}",
#         "Content-Type": "application/json"
#     }
#     data = {
#         "model": "tts-1",
#         "input": text,
#         "voice": "nova", # nova: 다정하고 상냥한 여성 톤 / alloy: 중성적 톤 / onyx: 남성 톤
#         "response_format": "mp3" 
#     }
    
#     print(f"[TTS] 🎙️ 음성 생성 요청 중... (Text: {text[:15]}...)")
    
#     async with httpx.AsyncClient() as client:
#         response = await client.post(url, headers=headers, json=data, timeout=30.0)
        
#         if response.status_code == 200:
#             # 스트리밍으로 받아서 파일로 저장 (aiofiles 사용)
#             async with aiofiles.open(save_path, 'wb') as f:
#                 await f.write(response.content)
#             print(f"[TTS] ✅ 음성 파일 생성 완료: {save_path}")
#             return static_url
#         else:
#             print(f"[TTS Error] 음성 생성 실패: {response.text}")
#             return None

# ==========================================
# 무료 Edge-TTS 생성 함수
# ==========================================
async def generate_tts_audio_edge(text: str, job_id: str) -> str:
    """Edge-TTS를 사용하여 무료로 고음질 음성을 생성합니다."""
    today_str = datetime.now().strftime("%Y%m%d")
    base_dir = os.path.join("/app/uploads/greeting_voice", today_str)
    os.makedirs(base_dir, exist_ok=True)
    
    file_name = f"greet_{job_id}.mp3"
    save_path = os.path.join(base_dir, file_name)
    static_url = f"{settings.BACKEND_URL}static/greeting_voice/{today_str}/{file_name}"
    
    voice = "ko-KR-SunHiNeural"
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(save_path)
        print(f"[TTS] ✅ 안부 음성 생성 완료: {save_path}")
        return static_url
    except Exception as e:
        print(f"[TTS Error] 음성 생성 실패: {e}")
        return None

# ==========================================
# 2. AI 서버로 텍스트 생성 요청 전달
# ==========================================
async def generate_greeting_text(dependent_name: str) -> str:
    """
    백엔드는 AI 서버로 데이터만 전달합니다.
    (프롬프트 생성 및 GX10 호출은 AI 서버가 담당)
    """
    # TODO: 실제 AI 서버의 엔드포인트 주소로 변경해주세요.
    ai_server_url = f"{settings.AI_PROXY_URL}/api/v1/generate-greeting" 
    
    # 시간대 정보 정도만 파라미터로 넘겨주면, AI 서버가 이를 받아 프롬프트를 구성하기 편합니다.
    now = datetime.now()
    if now.hour < 11:
        time_context = "아침"
    elif now.hour < 17:
        time_context = "오후"
    else:
        time_context = "저녁"


    headers = {
            "Authorization": f"Bearer {settings.AI_SECRET_TOKEN}",
            "Content-Type": "application/json"
        }

    payload = {
        "name": dependent_name,
        "time_context": time_context
    }

    try:
        print(f"[Backend] 📡 AI 서버로 {dependent_name} 어르신의 안부 텍스트 생성 요청 중...")
        
        # 비동기 HTTP 요청으로 대기 시간 동안 백엔드 블로킹 방지
        async with aiohttp.ClientSession() as session:
            # timeout을 적절히 주어 AI/GX10 서버 응답 지연 시 대비
            async with session.post(ai_server_url, headers=headers, json=payload, timeout=60) as response:
                if response.status == 200:
                    data = await response.json()
                    # AI 서버가 응답해주는 JSON 키 구조에 맞춰 수정하세요 (예: data["text"])
                    greeting_text = data.get("greeting_text", "")
                    
                    print(f"[Backend] ✅ AI 서버(GX10)로부터 안부 수신 완료: {greeting_text}")
                    return greeting_text
                else:
                    print(f"[Backend Error] AI 서버 응답 에러 (상태 코드: {response.status})")
                    raise ValueError("AI Server Response Error")
                    
    except Exception as e:
        print(f"[Backend Error] AI 서버 통신 실패: {e}")
        # 🚨 [안전빵 로직] AI 서버나 GX10 서버가 꺼져있거나 통신에 실패해도 
        # 스케줄러가 터지지 않고 기본 인사말을 반환하여 에지 기기에 전달되도록 방어합니다.
        return f"{dependent_name} 어르신, 오늘 하루는 어떻게 보내셨나요? 심심하시면 저랑 이야기 나눠요."

# ==========================================
# 3. 스케줄러 핵심 Job 함수
# ==========================================
async def proactive_greeting_job():
    print(f"⏰ [Scheduler] 선제적 안부 묻기 작업 시작...")
    db: Session = SessionLocal()
    
    try:
        # 🌟 핵심: 설정이 ON(True)인 어르신만 필터링!
        active_users = db.query(models.Dependent).join(
            models.DeviceSetting, 
            models.Dependent.id == models.DeviceSetting.dependent_id
        ).filter(models.DeviceSetting.proactive_greeting_enabled == True).all()

        if not active_users:
            print("알림을 보낼 대상이 없습니다. (모두 OFF 상태)")
            return

        for user in active_users:
            # 1. LLM 글귀 생성
            greeting_text = await generate_greeting_text(user.name)
            
            # 2. TTS 음성 파일 변환
            job_id = str(uuid.uuid4())[:8]
            audio_url = await generate_tts_audio_edge(greeting_text, job_id)
            
            # 3. 해당 어르신이 현재 웹소켓에 접속 중인지 확인 후 전송
            if audio_url and user.id in device_ws_manager.active_connections:
                payload = {
                    "action": "PROACTIVE_GREETING_ARRIVED",
                    "data": {
                        "text": greeting_text,
                        "audio_url": audio_url
                    }
                }
                await device_ws_manager.send_personal_message(payload, user.id)
                print(f"💌 [{user.name}] 어르신 기기로 안부 전송 완료!")
            else:
                print(f"💤 [{user.name}] 어르신 기기가 꺼져있거나 오프라인입니다.")
                
    except Exception as e:
        print(f"🚨 스케줄러 실행 중 오류 발생: {e}")
    finally:
        db.close()