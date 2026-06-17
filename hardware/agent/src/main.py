import asyncio
import websockets
import json
import aiohttp
import os
import tempfile
#import speech_recognition as sr
import time

# 🔗 환경 설정
BACKEND_URL = "http://host.docker.internal:8000"
LOCAL_LLM_URL = "http://localhost:8000/v1/chat/completions" # llama.cpp 서버 주소
DEPENDENT_ID = "dep_003" 

# --- 1. [로컬] STT 함수 (더미 제거, 실제 마이크 연동) ---
def recognize_speech_from_mic():
    # recognizer = sr.Recognizer()
    # with sr.Microphone() as source:
    #     print("🎙️ 어르신 말씀 듣는 중...")
    #     try:
    #         # 💡 개발자님이 직접 타임아웃 및 노이즈 세팅을 조정하세요.
    #         audio = recognizer.listen(source, timeout=10, phrase_time_limit=5)
    #         text = recognizer.recognize_google(audio, language="ko-KR")
    #         print(f"📝 [STT 인식 완료]: '{text}'")
    #         return text
    #     except sr.WaitTimeoutError:
    #         return "" # 침묵 시 빈 문자열 반환
    #     except Exception as e:
    #         print(f"⚠️ STT 오류: {e}")
    #         return ""
    print("🎙️ [테스트 모드] 마이크가 없으므로 가짜 음성을 생성합니다... (2초 대기)")
    time.sleep(2) # 실제로 말하고 인식하는 것처럼 2초 대기
    
    dummy_text = "지난번 우리 손주 이름이 뭐였지?"
    print(f"📝 [가상 인식 완료]: {dummy_text}")
    return dummy_text

    

def analyze_audio_level():
    # 💡 개발자님이 직접 RMS/VAD 로직을 구현하세요.
    return "silence"


# --- 2. [로컬] Jetson 엣지 Qwen 1.8B 라우터 ---
async def analyze_with_local_llm(session: aiohttp.ClientSession, raw_text: str):
    print("🧠 [Local LLM] Qwen 1.8B 추론 시작...")
    
    # 예외: 텍스트가 없는 경우 LLM을 거치지 않고 즉시 반환
    if not raw_text.strip():
        return {
            "intent": "CHAT",
            "privacy_flag": False,
            "safe_text": "",
            "local_action": "filler_hmm.mp3",
            "acoustic_event": analyze_audio_level()
        }

    # Qwen 1.8B에게 전달할 시스템 프롬프트 (JSON 형식 강제)
    system_prompt = """
    당신은 텍스트를 분석하여 JSON 형태로만 반환하는 라우터입니다.
    사용자의 말에 "비밀로 해", "말하지 마", "지워" 등의 내용이 있다면 privacy_flag를 true로 설정하고, safe_text에 구체적 인물/사건을 가린 요약본을 적으세요.
    반드시 아래 JSON 형식만 출력하세요:
    {"intent": "RAG_REQ", "privacy_flag": false, "safe_text": "원문 또는 요약문", "local_action": "play_filler.mp3"}
    """

    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": raw_text}
        ],
        "temperature": 0.1, # 일관된 JSON 출력을 위해 낮춤
        "response_format": {"type": "json_object"} # llama.cpp JSON 강제 옵션
    }

    try:
        async with session.post(LOCAL_LLM_URL, json=payload) as resp:
            if resp.status == 200:
                result = await resp.json()
                llm_output = result["choices"][0]["message"]["content"]
                routing_data = json.loads(llm_output)
                routing_data["acoustic_event"] = None
                return routing_data
            else:
                print(f"❌ 로컬 LLM 에러 (Status: {resp.status})")
    except Exception as e:
        print(f"❌ 로컬 LLM 서버 연결 실패: {e}")

    # Fallback (안전망: Qwen 응답 실패 시 기본값)
    return {
        "intent": "CHAT",
        "privacy_flag": False,
        "safe_text": raw_text,
        "local_action": None,
        "acoustic_event": None
    }


# --- 3. [로컬] 호응음 재생 ---
async def play_local_action(action_file: str):
    if not action_file: return
    print(f"🔊 [Local Audio] 즉각적인 호응 재생: {action_file}")
    # 💡 개발자님이 직접 mpg123 또는 pygame 코드를 넣으세요.
    await asyncio.sleep(0.1) 


# --- 4. [클라우드] 백엔드 전송 및 폴링 ---
async def dispatch_to_backend(session: aiohttp.ClientSession, routing_data: dict, raw_text: str):
    # 프라이버시 플래그 적용
    final_text = routing_data["safe_text"] if routing_data.get("privacy_flag") else raw_text
    
    payload = {
        "text": final_text,
        "intent": routing_data.get("intent"),
        "privacy_flag": routing_data.get("privacy_flag"),
        "acoustic_event": routing_data.get("acoustic_event")
    }

    trigger_url = f"{BACKEND_URL}/api/v1/memory/ask_text/{DEPENDENT_ID}"
    
    try:
        async with session.post(trigger_url, json=payload) as resp:
            if resp.status != 202: return "백엔드 연결 오류", None
            job_id = (await resp.json()).get("job_id")
    except Exception:
        return "인터넷 연결이 불안정합니다.", None

    status_url = f"{BACKEND_URL}/api/v1/memory/check_status/{job_id}"
    for _ in range(30):
        await asyncio.sleep(0.5) 
        try:
            async with session.get(status_url) as status_resp:
                if status_resp.status == 200:
                    status_data = await status_resp.json()
                    if status_data.get("status") == "COMPLETED":
                        return status_data.get("reply_text"), status_data.get("audio_url")
                    elif status_data.get("status") == "FAILED":
                        return "답변 생성에 실패했습니다.", None
        except Exception:
            continue
            
    return "시간이 초과되었습니다.", None


# --- 5. 클라우드 오디오 재생 ---
async def play_audio_from_url(session: aiohttp.ClientSession, audio_url: str):
    if not audio_url: return
    print(f"🔊 [Cloud Audio] 다운로드 및 재생: {audio_url}")
    # 💡 임시 파일 생성 및 재생 로직을 직접 구현하세요.


# --- 6. 메인 웹소켓 핸들러 ---
async def handle_client(websocket, path):
    print("✅ 웹소켓 연결 성공!")
    async with aiohttp.ClientSession() as session:
        try:
            async for message in websocket:
                data = json.loads(message)
                if data.get("command") == "force_record":
                    
                    await websocket.send(json.dumps({"status": "listening"}))
                    raw_text = await asyncio.to_thread(recognize_speech_from_mic)
                    
                    await websocket.send(json.dumps({"status": "processing"}))
                    
                    # 💡 세션(ClientSession)을 넘겨 HTTP API 방식으로 Qwen 호출
                    routing_data = await analyze_with_local_llm(session, raw_text)
                    
                    if routing_data.get("local_action"):
                        asyncio.create_task(play_local_action(routing_data["local_action"]))
                        
                    ai_response_text, audio_url = await dispatch_to_backend(session, routing_data, raw_text)

                    await websocket.send(json.dumps({
                        "status": "speaking",
                        "type": "AI_RESPONSE",
                        "text": ai_response_text
                    }))
                    
                    if audio_url:
                        await play_audio_from_url(session, audio_url)
                    
                    await websocket.send(json.dumps({"status": "idle"}))

        except websockets.exceptions.ConnectionClosed:
            print("❌ 연결 종료")

async def main():
    server = await websockets.serve(handle_client, "0.0.0.0", 8765)
    print("🚀 Jetson 엣지 에이전트 시작됨 (ws://0.0.0.0:8765)")
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())