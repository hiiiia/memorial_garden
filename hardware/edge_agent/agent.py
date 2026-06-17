import asyncio
import websockets
import json
import requests
import time

# 엣지 LLM(llama.cpp) 주소
LLM_API_URL = "http://127.0.0.1:8080/completion"

# ==========================================
# 🎤 하드웨어 제어 모듈 (STT / TTS)
# ==========================================
async def start_stt_recording():
    """
    [마이크 녹음 및 STT 로직 구현부]
    실제 환경에서는 여기에 PyAudio, SpeechRecognition, 또는 Whisper API를 연결합니다.
    """
    print("🎙️ [하드웨어] 마이크 활성화. 어르신 말씀 듣는 중...")
    
    # 임시 대기 시간 (실제 음성 인식 시간으로 대체됨)
    await asyncio.sleep(3) 
    
    # 테스트용 하드코딩된 음성 인식 결과 반환
    recognized_text = "오늘 시장에 가서 나물도 사고 참 재밌었어." 
    print(f"📥 [STT 변환 완료] 인식된 문장: {recognized_text}")
    
    return recognized_text

async def play_tts_audio(text):
    """
    [TTS 오디오 재생 로직 구현부]
    실제 환경에서는 gTTS, Google Cloud TTS, 또는 로컬 오디오 재생 명령어(aplay 등)를 연결합니다.
    """
    print(f"🔊 [하드웨어] 스피커 재생 시작: {text}")
    
    # 글자 수에 비례하여 말하는 시간 시뮬레이션 (초당 약 5글자)
    play_duration = len(text) / 5.0
    await asyncio.sleep(play_duration) 
    
    print("🔇 [하드웨어] 스피커 재생 완료")

# ==========================================
# 🧠 메인 에이전트 라우팅 및 통신 로직
# ==========================================
async def chat_handler(websocket):
    print("✅ [웹소켓] React 프론트엔드 연결 성공!")
    
    try:
        async for message in websocket:
            data = json.loads(message)
            
            # 1️⃣ React에서 '말하기' 버튼(force_record)을 눌렀을 때
            if data.get('command') == 'force_record':
                
                # [상태 업데이트] UI를 'listening(말씀을 듣고 있어요...)'으로 변경
                await websocket.send(json.dumps({"status": "listening"}))
                
                # 마이크를 열고 어르신 말씀 듣기 (STT)
                user_text = await start_stt_recording()

                # 2️⃣ [상태 업데이트] UI를 'processing(생각하는 중이에요...)'으로 변경
                await websocket.send(json.dumps({"status": "processing"}))
                
                # LLM 프롬프트 세팅 (어르신 맞춤형 다정한 챗봇 페르소나 적용)
                prompt = f"""<|im_start|>system
당신은 독거노인을 위한 따뜻하고 다정한 반려 로봇 '기억정원'입니다. 
어르신의 말에 공감하고, 짧고 이해하기 쉬운 한국어(해요체)로 대답하세요. 최대 2문장으로 짧게 말하세요.
<|im_end|>
<|im_start|>user
{user_text}<|im_end|>
<|im_start|>assistant
"""
                payload = {
                    "prompt": prompt,
                    "n_predict": 128,
                    "temperature": 0.6,
                    "stop": ["<|im_end|>"]
                }

                try:
                    # 엣지 LLM으로 추론 요청 (동기 함수인 requests를 비동기 루프에서 안전하게 실행)
                    loop = asyncio.get_running_loop()
                    response = await loop.run_in_executor(
                        None, 
                        lambda: requests.post(LLM_API_URL, json=payload).json()
                    )
                    
                    ai_text = response['content'].strip()
                    print(f"🤖 [LLM 응답 생성] {ai_text}")

                    # 3️⃣ [상태 업데이트] UI를 'speaking(이야기하고 있어요...)'으로 변경하고 텍스트 전달
                    await websocket.send(json.dumps({
                        "status": "speaking",
                        "type": "AI_RESPONSE",
                        "text": ai_text
                    }))

                    # 스피커로 음성 출력 (TTS)
                    await play_tts_audio(ai_text)

                    # 4️⃣ [상태 업데이트] 대화가 끝났으므로 대기 상태(idle)로 복귀
                    await websocket.send(json.dumps({"status": "idle"}))
                    print("🏁 [대화 사이클 완료] 다음 입력을 대기합니다.")

                except Exception as e:
                    error_msg = f"LLM 연동 에러가 발생했습니다: {str(e)}"
                    print(f"❌ [에러] {error_msg}")
                    await websocket.send(json.dumps({
                        "status": "idle",
                        "type": "AI_RESPONSE",
                        "text": "어르신, 잠시 생각이 엉켰어요.\n다시 말씀해 주시겠어요?"
                    }))

    except websockets.exceptions.ConnectionClosed:
        print("❌ [웹소켓] React 프론트엔드 연결 해제됨")

async def main():
    print("🚀 [기억정원 Agent] ws://localhost:8765 에서 대기 중...")
    async with websockets.serve(chat_handler, "localhost", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())