import asyncio
import websockets
import json
import aiohttp
import os
import time

# ==========================================
# 🔗 환경 설정 (라즈베리 파이 Docker 환경)
# ==========================================
# AI 서버이자 백엔드인 PC의 IP 및 포트
AI_SERVER_URL = os.getenv("AI_SERVER_URL", "http://192.168.1.82:8000") 
DEPENDENT_ID = "dep_003" 

# ==========================================
# 🎤 1. [로컬] STT 및 오디오 분석 모듈
# ==========================================
def recognize_speech_from_mic():
    print("🎙️ [하드웨어] 마이크 활성화. 어르신 말씀 듣는 중... (2초 대기)")
    time.sleep(2) 
    
    # 💡 테스트용 더미 텍스트
    dummy_text = "저번에 우리 손주가 언제 왔었지?" 
    
    print(f"📝 [STT 인식 완료]: {dummy_text}")
    return dummy_text

def analyze_audio_level():
    return "silence"

# ==========================================
# 🧠 2. [오케스트레이터 호출] AI 서버 연동 API
# ==========================================
async def get_response_from_ai_server(session: aiohttp.ClientSession, raw_text: str):
    """
    라즈베리 파이는 판단하지 않고, 모든 텍스트를 AI 서버의 라우터로 넘깁니다.
    AI 서버가 RAG 여부를 판단하고 최종 답변(local_reply)을 만들어 돌려줍니다.
    """
    print("🧠 [Edge] AI 서버(GX10)에 응답을 요청합니다...")
    
    if not raw_text.strip():
        return {
            "intent": "SIMPLE_CHAT", "privacy_flag": False, "safe_text": "", 
            "local_action": "filler_hmm.mp3", "acoustic_event": analyze_audio_level(),
            "local_reply": "어르신, 제가 잘 못 들었어요. 다시 말씀해 주시겠어요?"
        }

    route_url = f"{AI_SERVER_URL}/api/v1/edge/route"
    payload = {
        "user_id": DEPENDENT_ID,
        "text": raw_text
    }
    
    try:
        async with session.post(route_url, json=payload, timeout=10.0) as resp:
            if resp.status == 200:
                routing_data = await resp.json()
                print(f"✅ [AI Server 응답 도착]: {routing_data}")
                routing_data["acoustic_event"] = analyze_audio_level()
                return routing_data
            else:
                print(f"⚠️ [AI Server 에러] 상태 코드: {resp.status}")
                raise Exception("서버 응답 오류")

    except Exception as e:
        print(f"❌ AI 서버 통신 실패: {e}")
        return {
            "intent": "SIMPLE_CHAT", "privacy_flag": False, "safe_text": raw_text,
            "local_action": None, "acoustic_event": None, 
            "local_reply": "네 어르신, 제가 귀 기울여 듣고 있어요."
        }

# ==========================================
# 🔊 3. [메인 보드] 오디오 재생 제어
# ==========================================
async def play_local_action(action_file: str):
    if not action_file: return
    print(f"🔊 [Local Audio] 추임새/효과음 재생 (딜레이 0초): {action_file}")
    await asyncio.sleep(0.1) 

# ==========================================
# ☁️ 4. [클라우드] 백엔드 심층 분석 로깅 (비동기)
# ==========================================
async def dispatch_to_backend_async_log(session: aiohttp.ClientSession, routing_data: dict, raw_text: str):
    """
    어르신에게 답변이 나간 직후, 백그라운드에서 백엔드 심층 분석 파이프라인으로 데이터를 던집니다.
    """
    final_text = routing_data["safe_text"] if routing_data.get("privacy_flag") else raw_text
    
    # 추후 백엔드의 실제 로깅/분석 엔드포인트에 맞춰 URL 변경 가능
    log_url = f"{AI_SERVER_URL}/api/v1/analyze" 
    payload = {
        "job_id": f"job_{int(time.time())}",
        "user_id": DEPENDENT_ID,
        "file_path": "dummy_path_for_text_only.wav",
        "callback_url": "http://localhost:8000/internal/callback" # 임시
    }
    
    try:
        async with session.post(log_url, json=payload, timeout=5.0) as resp:
            if resp.status in (200, 202):
                print("📨 [Background Log] 심층 분석용 헬스케어 메타데이터 적재 요청 완료")
    except Exception as e:
        print(f"❌ [Background Log] 백엔드 로깅 실패: {e}")

# ==========================================
# 🔀 5. 메인 웹소켓 컨트롤러
# ==========================================
async def handle_client(websocket, path="/"):
    print("✅ [웹소켓] React 프론트엔드 연결 성공!")
    async with aiohttp.ClientSession() as session:
        try:
            async for message in websocket:
                data = json.loads(message)
                
                if data.get("command") == "force_record":
                    await websocket.send(json.dumps({"status": "listening"}))
                    raw_text = await asyncio.to_thread(recognize_speech_from_mic)
                    
                    await websocket.send(json.dumps({"status": "processing"}))
                    
                    # 1. AI 서버로 모든 판단과 조합을 위임 (단일 호출)
                    routing_data = await get_response_from_ai_server(session, raw_text)
                    
                    # 2. 추임새가 있다면 즉시 재생
                    if routing_data.get("local_action"):
                        asyncio.create_task(play_local_action(routing_data.get("local_action")))
                    
                    # 3. AI 서버가 완성해준 최종 텍스트 추출
                    ai_response_text = routing_data.get("local_reply", "기억 창고를 찾고 있어요..")
                    
                    # 4. 즉시 프론트엔드에 음성 출력 지시 (레이턴시 최소화)
                    await websocket.send(json.dumps({
                        "status": "speaking",
                        "type": "AI_RESPONSE",
                        "text": ai_response_text
                    }))
                    
                    # 5. 대화 내역 백엔드 비동기 전송
                    asyncio.create_task(dispatch_to_backend_async_log(session, routing_data, raw_text))
                    
                    await websocket.send(json.dumps({"status": "idle"}))
                    
        except websockets.exceptions.ConnectionClosed:
            print("❌ [웹소켓] React와의 연결이 해제되었습니다.")

async def main():
    print("🚀 [Raspberry Pi Edge Agent] ws://0.0.0.0:8765 에서 대기 중...")
    async with websockets.serve(handle_client, "0.0.0.0", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())