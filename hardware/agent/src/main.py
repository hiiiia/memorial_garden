import asyncio
import websockets
import json
import aiohttp
import speech_recognition as sr
import os
from gtts import gTTS
import tempfile # 임시 음성 파일 생성용

# --- 기존 STT 함수 (유지) ---
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

# --- 새로 추가된 TTS 재생 함수 ---
def speak_text(text: str):
    """텍스트를 음성으로 변환하고 스피커로 출력하는 함수"""
    # UI용 태그나 괄호 안의 에러 메시지는 읽지 않도록 필터링
    if text.startswith("("):
        return

    print(f"🔊 스피커 출력 준비: {text}")
    try:
        # 1. 텍스트를 한국어 음성(mp3)으로 변환
        tts = gTTS(text=text, lang='ko')
        
        # 2. 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            temp_path = fp.name
        tts.save(temp_path)
        
        # 3. mpg123 프로그램으로 스피커 출력 (-q 옵션으로 터미널 지저분한 로그 숨김)
        os.system(f"mpg123 -q {temp_path}")
        
        # 4. 재생이 끝나면 임시 파일 삭제
        os.remove(temp_path)
        print("✅ 스피커 출력 완료")
    except Exception as e:
        print(f"❌ TTS 에러 발생: {e}")

# --- 라우팅 함수 (유지) ---
def should_query_backend(text: str) -> bool:
    keywords = ["기억", "지난번", "언제", "했던", "그때", "이름", "가족", "어제", "저번"]
    return any(keyword in text for keyword in keywords)

# --- 메인 웹소켓 핸들러 ---
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
                    
                    if user_text.startswith("("):
                        ai_response = "어르신, 다시 한 번 말씀해 주시겠어요?"
                    else:
                        if should_query_backend(user_text):
                            print("🌐 [Router] 백엔드 RAG 서버로 조회 요청")
                            ai_response = f"백엔드 검색 결과: '{user_text}'에 대한 답변입니다."
                        else:
                            print("⚡ [Router] 로컬 즉시 응답 생성")
                            ai_response = f"어르신이 '{user_text}'라고 말씀하셨군요!"
                    
                    print(f"✅ AI 응답 생성 완료: {ai_response}")

                    # 3단계: 말하는 중 (웹소켓으로 자막 쏘고, 스피커로 소리 내기)
                    await websocket.send(json.dumps({
                        "status": "speaking",
                        "type": "AI_RESPONSE",
                        "text": ai_response
                    }))
                    
                    # ⭐️ 텍스트를 스피커로 실제 출력 (비동기 스레드로 실행하여 멈춤 방지)
                    await asyncio.to_thread(speak_text, ai_response)
                    
                    # 4단계: 대기 복귀
                    await websocket.send(json.dumps({"status": "idle"}))
                    print("💤 대기 모드로 전환")

        except websockets.exceptions.ConnectionClosed:
            print("❌ 프론트엔드 연결이 끊어졌습니다.")

async def main():
    server = await websockets.serve(handle_client, "0.0.0.0", 8765)
    print("🚀 파이썬 하드웨어 에이전트 시작됨 (ws://0.0.0.0:8765)")
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())