import asyncio
import websockets
import json
import aiohttp
import os
import time
from config import settings
from database import db_manager 


# ==========================================
# 🔗 환경 설정 (라즈베리 파이 Docker 환경)
# ==========================================
AI_SERVER_URL = settings.AI_SERVER_URL
DEPENDENT_ID = settings.DEPENDENT_ID

# ==========================================
# 🎤 1. [로컬] STT 및 오디오 분석 모듈
# ==========================================
def recognize_speech_from_mic():
    print("🎙️ [하드웨어] 마이크 활성화. 어르신 말씀 듣는 중... (2초 대기)")
    time.sleep(2) 
    
    # 💡 테스트 시 시나리오에 맞게 더미 텍스트를 변경해보세요.
    dummy_text = "우리 며느리랑 돈 때문에 서운했던 게 언제였더라?" 
    
    print(f"📝 [STT 인식 완료]: {dummy_text}")
    return dummy_text

def analyze_audio_level():
    return "silence"

# ==========================================
# 🧠 2. [오케스트레이터 호출] AI 서버 연동 API
# ==========================================
# 로컬에서 찾아낸 과거 기억 맥락(memory_context)을 매개변수로 추가받습니다.
async def get_response_from_ai_server(session: aiohttp.ClientSession, raw_text: str, memory_context: str = ""):
    """
    라즈베리 파이에서 검색한 로컬 기억(Context)과 어르신의 발화를 묶어 
    외부 AI 서버(GX10)의 라우터로 전달하여 문장을 생성합니다.
    """
    print("🧠 [Edge] AI 서버(GX10)에 응답을 요청합니다...")
    
    if not raw_text.strip():
        return {
            "intent": "SIMPLE_CHAT", "privacy_flag": False, "safe_text": "", 
            "local_action": "filler_hmm.mp3", "acoustic_event": analyze_audio_level(),
            "local_reply": "어르신, 제가 잘 못 들었어요. 다시 말씀해 주시겠어요?",
            "save_flag": False
        }

    route_url = f"{AI_SERVER_URL}/api/v1/edge/route"
    
    # AI 서버가 RAG 연산을 중복으로 하지 않도록 엣지가 찾은 기억을 페이로드에 주입
    payload = {
        "user_id": DEPENDENT_ID,
        "text": raw_text,
        "memory_context": memory_context  
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
        # 서버 다운 시 작동할 최후의 보루 (Fallback)
        fallback_reply = "네 어르신, 제가 귀 기울여 듣고 있어요."
        if memory_context:
            # 외부망 차단 상태여도 로컬 DB에 기억이 있다면 최소한의 정보 제공
            fallback_reply = f"어르신, 외부 네트워크 연결이 원활하지 않지만 로컬 기억 저장소에 관련 기록이 남아있어요."
            
        return {
            "intent": "SIMPLE_CHAT", "privacy_flag": False, "safe_text": raw_text,
            "local_action": None, "acoustic_event": None, 
            "local_reply": fallback_reply, "save_flag": False
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
    # 프라이버시 플래그가 True면 철저히 비식별화된 safe_text만 서버 대시보드로 보냄
    final_text = routing_data["safe_text"] if routing_data.get("privacy_flag") else raw_text
    log_url = f"{AI_SERVER_URL}/api/v1/analyze" 
    
    payload = {
        "job_id": f"job_{int(time.time())}",
        "user_id": DEPENDENT_ID,
        "file_path": "dummy_path_for_text_only.wav",
        "text_log": final_text, # 분석용 로그에 비식별화 처리된 텍스트 바인딩
        "callback_url": "http://localhost:8000/internal/callback"
    }
    
    headers = {
        "Authorization": f"Bearer {settings.HW_TOKEN}" 
    }
    
    try:
        async with session.post(log_url, json=payload, headers=headers, timeout=5.0) as resp:
            if resp.status in (200, 202):
                print(f"📨 [Background Log] 심층 분석용 헬스케어 메타데이터 적재 완료 (데이터: {final_text[:15]}...)")
            else:
                print(f"⚠️ [Background Log] 로깅 거절됨 (상태 코드: {resp.status})")
    except Exception as e:
        print(f"❌ [Background Log] 백엔드 로깅 실패: {e}")


# ==========================================
# 🔀 5. 메인 웹소켓 컨트롤러
# ==========================================
async def handle_client(websocket, path="/"):
    print("✅ [웹소켓] React 프론트엔드 연결 성공!")
    async with aiohttp.ClientSession() as session:
        try:
            async_tasks = set()
            async for message in websocket:
                data = json.loads(message)
                
                if data.get("command") == "force_record":
                    await websocket.send(json.dumps({"status": "listening"}))
                    raw_text = await asyncio.to_thread(recognize_speech_from_mic)
                    
                    await websocket.send(json.dumps({"status": "processing"}))
                    
                    # 1단계 [온디바이스 RAG]: 서버로 가기 전, 라즈베리 로컬 DB에서 유사 기억 파싱
                    # 치매 예방용 구체성을 로컬 기기 내부에서만 조회합니다.
                    search_results = db_manager.search_memory(raw_text, limit=1)
                    memory_context = ""
                    if search_results:
                        found_memory = search_results[0]
                        memory_context = f"어르신의 과거 기억 (날짜: {found_memory['date']}): {found_memory['content']}"
                        print(f"💡 [Local RAG] 로컬 기억 매칭 확인 -> 서버 가이드로 주입")
                    
                    # 2단계 [네트워크 최적화]: 원문과 로컬 컨텍스트를 함께 AI 서버로 위임
                    routing_data = await get_response_from_ai_server(session, raw_text, memory_context)
                    
                    # 3단계 [온디바이스 격리 적재]: AI 서버가 기억해야 할 사실정보라고 판정(save_flag)하면 로컬에 적재
                    # 원본 데이터는 외부 클라우드 DB가 아닌 어르신 댁의 라즈베리 파이에 안전하게 고립 보관됩니다.
                    if routing_data.get("save_flag", False):
                        db_manager.insert_memory(raw_text)
                    
                    # 4단계: 추임새 처리
                    if routing_data.get("local_action"):
                        task = asyncio.create_task(play_local_action(routing_data.get("local_action")))
                        async_tasks.add(task)
                        task.add_done_callback(async_tasks.discard)
                    
                    # 5단계: 최종 가공 답변 추출 및 프론트엔드 발화 지시
                    ai_response_text = routing_data.get("local_reply", "기억 창고를 찾고 있어요..")
                    await websocket.send(json.dumps({
                        "status": "speaking",
                        "type": "AI_RESPONSE",
                        "text": ai_response_text
                    }))
                    
                    # 6단계 [이중 파이프라인 완성]: 대화 내역은 비식별화(safe_text) 처리된 데이터로 서버 로깅
                    log_task = asyncio.create_task(dispatch_to_backend_async_log(session, routing_data, raw_text))
                    async_tasks.add(log_task)
                    log_task.add_done_callback(async_tasks.discard)
                    
                    await websocket.send(json.dumps({"status": "idle"}))
                    
        except websockets.exceptions.ConnectionClosed:
            print("❌ [웹소켓] React와의 연결이 해제되었습니다.")

async def main():
    print("🚀 [Raspberry Pi Edge Agent] ws://0.0.0.0:8765 에서 대기 중...")
    async with websockets.serve(handle_client, "0.0.0.0", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())