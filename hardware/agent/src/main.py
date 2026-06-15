import asyncio
import websockets
import json
import aiohttp
import speech_recognition as sr
import os
import tempfile

# 🔗 백엔드 서버 실제 주소 설정
BACKEND_URL = "http://localhost:8000"  # 실배포 시 백엔드 실제 IP로 변경

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

async def fetch_and_play_tts(session: aiohttp.ClientSession, text: str):
    if text.startswith("("):
        return
    print(f"🌐 [TTS] 백엔드 음성 생성 요청: {text}")
    try:
        async with session.post(f"{BACKEND_URL}/tts", json={"text": text}) as resp:
            if resp.status == 200:
                audio_data = await resp.read()
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                    temp_path = fp.name
                    fp.write(audio_data)
                
                print("🔊 스피커 재생 시작")
                await asyncio.to_thread(os.system, f"mpg123 -q {temp_path}")
                os.remove(temp_path)
            else:
                print(f"❌ TTS 요청 실패 (Status: {resp.status})")
    except Exception as e:
        print(f"❌ TTS 재생 에러: {e}")

def should_query_backend(text: str) -> bool:
    keywords = ["기억", "지난번", "언제", "했던", "그때", "이름", "가족", "어제", "저번", "일기", "추억"]
    return any(keyword in text for keyword in keywords)

# --- 🧠 메인 통신 핸들러 ---
async def handle_client(websocket, path):
    print("✅ 프론트엔드(React) 웹소켓 연결 성공!")
    
    async with aiohttp.ClientSession() as session:
        try:
            async for message in websocket:
                data = json.loads(message)
                if data.get("command") == "force_record":
                    
                    # 1단계: 음성 인식 (STT)
                    await websocket.send(json.dumps({"status": "listening"}))
                    user_text = await asyncio.to_thread(recognize_speech_from_mic)
                    print(f"📝 인식된 텍스트: {user_text}")
                    
                    # 2단계: 대화 상태 분류 및 처리 (처리 중 UI)
                    await websocket.send(json.dumps({"status": "processing"}))
                    
                    # 예외 처리: 소리를 전혀 인식하지 못했을 때
                    if user_text.startswith("("):
                        ai_response = "어르신, 조금 더 크고 또박또박 말씀해 주시겠어요?"
                    else:
                        # RAG 조회가 필요한 문장인지 판단
                        if should_query_backend(user_text):
                            print("🌐 [Router] 백엔드 RAG 서버로 조회 요청 시작")
                            
                            try:
                                # 💡 어르신 서비스 특성상 5초 이내에 답변이 안 오면 타임아웃 처리
                                async with session.post(
                                    f"{BACKEND_URL}/query", 
                                    json={
                                        "user_id": "user_kim",  # 특정 어르신의 기억 매핑용 ID
                                        "text": user_text
                                    },
                                    timeout=aiohttp.ClientTimeout(total=5.0)
                                ) as resp:
                                    if resp.status == 200:
                                        result = await resp.json()
                                        # 백엔드 API 명세에 맞춰 key값 설정 (ex: answer 또는 response)
                                        ai_response = result.get("answer", "기억을 떠올리는 중 부품에 작은 혼선이 생겼나 봐요.")
                                    else:
                                        print(f"❌ 백엔드 RAG 응답 에러 (Status: {resp.status})")
                                        ai_response = "죄송해요 어르신, 방금 하신 말씀은 제가 기억 창고에서 찾지 못했어요."
                            
                            except asyncio.TimeoutError:
                                print("❌ [Timeout] 백엔드 RAG 응답 시간 초과 (5초)")
                                ai_response = "기억을 떠올리는 데 시간이 조금 걸리네요. 조금 이따가 다시 한 번 물어봐 주세요."
                            except Exception as ce:
                                print(f"❌ [Connection Error] 백엔드 연결 불가능: {ce}")
                                ai_response = "인터넷 연결이 잠시 불안정해서 기억을 확인하기 어려워요. 죄송합니다."
                        
                        else:
                            # 로컬 리액션 처리 (단순 대화용 스크립트 분기)
                            print("⚡ [Router] 로컬 즉시 응답 생성")
                            ai_response = f"네 어르신, 방금 말씀하신 내용을 들으니 저도 기분이 참 좋네요. 항상 건강하셔요."
                    
                    print(f"✅ 최종 확정 응답: {ai_response}")

                    # 3단계: 음성 출력 및 자막 송신
                    await websocket.send(json.dumps({
                        "status": "speaking",
                        "type": "AI_RESPONSE",
                        "text": ai_response
                    }))
                    
                    # 백엔드 TTS 엔드포인트를 호출하여 스피커로 출력
                    await fetch_and_play_tts(session, ai_response)
                    
                    # 4단계: 시스템 대기 모드 복귀
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