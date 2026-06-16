import asyncio
import websockets
import json
import aiohttp
import speech_recognition as sr
import os
import tempfile

# 🔗 백엔드 서버 기본 주소 및 어르신 ID 세팅 (실제 환경에 맞게 변경)
BACKEND_URL = "http://localhost:8000" 
DEPENDENT_ID = "dep_03" 

# --- 1. STT 함수 (기존 유지) ---
def recognize_speech_from_mic():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("🎙️ 주변 소음 적응 중 (1초)...")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        print("🎙️ 어르신 말씀 듣는 중...")
        try:
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=5)
            print("⏳ 구글 STT로 텍스트 변환 중...")
            return recognizer.recognize_google(audio, language="ko-KR")
        except sr.WaitTimeoutError:
            return "(말씀이 없으셨습니다)"
        except Exception as e:
            return f"(오류 발생: {e})"

# --- 2. 🚀 [핵심] 백엔드 RAG 트리거 및 폴링 함수 ---
async def query_backend_with_polling(session: aiohttp.ClientSession, user_text: str):
    """백엔드에 처리를 맡기고 0.5초마다 완료 여부를 확인합니다."""
    if user_text.startswith("("):
        return "어르신, 다시 한 번 말씀해 주시겠어요?", None

    # 1단계: 백엔드에 텍스트 던지기 (Trigger)
    trigger_url = f"{BACKEND_URL}/api/v1/memory/ask_text/{DEPENDENT_ID}"
    print(f"🌐 [API] 백엔드로 텍스트 전송 중: {user_text}")
    
    try:
        async with session.post(trigger_url, json={"text": user_text}) as resp:
            if resp.status != 202:
                print(f"❌ 백엔드 요청 거부 (Status: {resp.status})")
                return "기억 창고와 연결이 끊어졌어요.", None
            
            result = await resp.json()
            job_id = result.get("job_id")
            print(f"✅ [Trigger] 접수 완료 (Job ID: {job_id}). 폴링 대기 시작...")
    except Exception as e:
        print(f"❌ 백엔드 연결 실패: {e}")
        return "인터넷 연결이 불안정하네요.", None

    # 2단계: 폴링 루프 (0.5초 간격, 최대 10초 대기)
    status_url = f"{BACKEND_URL}/api/v1/memory/check_status/{job_id}"
    max_retries = 20 
    
    for attempt in range(max_retries):
        await asyncio.sleep(0.5) 
        
        try:
            async with session.get(status_url) as status_resp:
                if status_resp.status == 200:
                    status_data = await status_resp.json()
                    current_status = status_data.get("status")
                    
                    if current_status == "COMPLETED":
                        print(f"✅ [Polling] 답변 생성 완료! (시도: {attempt+1}번)")
                        reply_text = status_data.get("reply_text")
                        audio_url = status_data.get("audio_url")
                        return reply_text, audio_url
                        
                    elif current_status == "FAILED":
                        print("❌ [Polling] 백엔드 처리 중 FAILED 발생")
                        return "제가 잠시 딴생각을 하느라 놓쳤네요. 다시 말씀해 주시겠어요?", None
                    
                    print(f"⏳ [Polling] AI 서버가 대답을 생성 중입니다... ({attempt+1}/{max_retries})")
        except Exception as e:
            print(f"❌ 상태 확인(Polling) 중 에러: {e}")
            
    # 3단계: 타임아웃
    print("❌ [Polling Timeout] 10초 초과. 대기 종료.")
    return "기억을 떠올리는 데 시간이 조금 걸리네요. 조금 이따 다시 여쭤볼게요.", None

# --- 3. 🎵 다운로드 및 오디오 재생 함수 ---
async def play_audio_from_url(session: aiohttp.ClientSession, audio_url: str):
    """백엔드가 알려준 URL에서 완성된 mp3를 받아 스피커로 재생합니다."""
    if not audio_url:
        return
        
    print(f"🔊 스피커 출력 준비 (오디오 다운로드): {audio_url}")
    try:
        async with session.get(audio_url) as resp:
            if resp.status == 200:
                audio_data = await resp.read()
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                    temp_path = fp.name
                    fp.write(audio_data)
                
                # 라즈베리 파이 스피커 재생 (-q 옵션으로 로그 숨김)
                await asyncio.to_thread(os.system, f"mpg123 -q {temp_path}")
                os.remove(temp_path)
                print("✅ 스피커 재생 완료 및 임시 파일 삭제")
            else:
                print(f"❌ 오디오 파일 다운로드 실패 (Status: {resp.status})")
    except Exception as e:
        print(f"❌ 오디오 재생 파이프라인 에러: {e}")

def should_query_backend(text: str) -> bool:
    keywords = ["기억", "지난번", "언제", "했던", "그때", "이름", "가족", "어제", "저번", "일기", "추억"]
    return any(keyword in text for keyword in keywords)

# --- 4. 메인 웹소켓 핸들러 ---
async def handle_client(websocket, path):
    print("✅ 프론트엔드(React) 웹소켓 연결 성공!")
    
    async with aiohttp.ClientSession() as session:
        try:
            async for message in websocket:
                data = json.loads(message)
                if data.get("command") == "force_record":
                    
                    # 1단계: 듣는 중
                    await websocket.send(json.dumps({"status": "listening"}))
                    user_text = await asyncio.to_thread(recognize_speech_from_mic)
                    print(f"📝 인식된 텍스트: {user_text}")
                    
                    # 2단계: 처리 중
                    await websocket.send(json.dumps({"status": "processing"}))
                    
                    # 🚀 백엔드 폴링 로직 태우기
                    if should_query_backend(user_text) and not user_text.startswith("("):
                        ai_response_text, audio_url = await query_backend_with_polling(session, user_text)
                    else:
                        print("⚡ [Router] 로컬 즉시 응답 (혹은 인식 실패)")
                        ai_response_text = "네 어르신, 제가 잘 듣고 있습니다."
                        audio_url = None

                    # 3단계: 말하는 중 (UI 자막 송신)
                    await websocket.send(json.dumps({
                        "status": "speaking",
                        "type": "AI_RESPONSE",
                        "text": ai_response_text
                    }))
                    
                    # 4단계: 백엔드에서 받은 실제 음성 출력
                    if audio_url:
                        await play_audio_from_url(session, audio_url)
                    
                    # 5단계: 대기 복귀
                    await websocket.send(json.dumps({"status": "idle"}))
                    print("💤 대기 모드로 전환\n")

        except websockets.exceptions.ConnectionClosed:
            print("❌ 프론트엔드 연결이 끊어졌습니다.")

async def main():
    server = await websockets.serve(handle_client, "0.0.0.0", 8765)
    print("🚀 파이썬 하드웨어 에이전트 시작됨 (ws://0.0.0.0:8765)")
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())