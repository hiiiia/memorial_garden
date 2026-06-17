import asyncio
import websockets
import json
import aiohttp
import os
import time
from openai import AsyncOpenAI

# ==========================================
# 🔗 환경 설정 (라즈베리 파이 Docker 환경)
# ==========================================
BACKEND_URL = os.getenv("BACKEND_URL", "http://192.168.1.82:8000") 
DEPENDENT_ID = "dep_003" 

# 🌟 GX10 외부 로컬 서버 (Ollama)
client = AsyncOpenAI(
    base_url="http://codu.ddns.net:11434/v1",
    api_key="ollama" 
)
LLM_MODEL = "qwen2.5:3b"

# ==========================================
# 🎤 1. [로컬] STT 및 오디오 분석 모듈
# ==========================================
def recognize_speech_from_mic():
    print("🎙️ [하드웨어] 마이크 활성화. 어르신 말씀 듣는 중... (2초 대기)")
    time.sleep(2) 
    
    # 💡 테스트를 위해 아래 문장을 번갈아가며 사용하세요.
    # dummy_text = "저번에 우리 손주가 언제 왔었지?" # -> RAG_REQ (동기화)
    dummy_text = "아이고, 오늘 비가 와서 그런가 무릎이 쑤시네." # -> SIMPLE_CHAT (비동기 로깅)
    
    print(f"📝 [STT 인식 완료]: {dummy_text}")
    return dummy_text

def analyze_audio_level():
    return "silence"

# ==========================================
# 🧠 2. [GX10 서버] 외부 엣지 LLM 라우터 (OpenAI 패키지)
# ==========================================
async def analyze_with_gx10_llm(raw_text: str):
    print(f"🧠 [GX10 Server] {LLM_MODEL} 라우팅 판단 시작...")
    
    if not raw_text.strip():
        return {
            "intent": "SIMPLE_CHAT", "privacy_flag": False, "safe_text": "", 
            "local_action": "filler_hmm.mp3", "acoustic_event": analyze_audio_level(),
            "local_reply": "어르신, 제가 잘 못 들었어요. 다시 말씀해 주시겠어요?"
        }

    # 🌟 10년 차 전문 복지사 페르소나 적용
    messages = [
        {
            "role": "system", 
            "content": """
당신은 경력 10년 차의 따뜻하고 숙련된 노인 전문 복지사 '기억정원'입니다. 
어르신의 일상을 세심하게 살피고, 언제나 존댓말(해요체)과 다정한 말투를 사용하세요.

[수행 임무]
1. 입력된 텍스트를 분석하여 JSON 형식으로만 응답하세요.
2. intent 구분:
   - RAG_REQ: 과거의 기억, 특정 인물, 일정, 약 복용 확인 등 클라우드 지식 DB 검색이 필요할 때.
   - SIMPLE_CHAT: 날씨, 통증 호소, 감정 표현(외로움, 기쁨 등) 등 단순 스몰톡 및 정서적 공감.
3. local_reply 작성 규칙:
   - 복지사로서 어르신의 말씀에 먼저 깊이 공감하고, 따뜻한 위로와 격려를 포함하세요.
   - 문장은 간결하고 이해하기 쉽게 2문장 내외로 작성하세요.
4. 프라이버시 보호: 사용자가 '비밀', '지워' 등 민감한 정보를 언급하면 privacy_flag를 true로 하고, safe_text에 '[발화 정보 보호됨]'을 입력하세요.

[JSON 형식]
{"intent": "RAG_REQ" 또는 "SIMPLE_CHAT", "privacy_flag": true/false, "safe_text": "원문/요약", "local_action": null, "local_reply": "복지사로서의 따뜻한 답변"}
"""
        },
        {"role": "user", "content": "저번에 우리 손주가 언제 왔었지?"},
        {"role": "assistant", "content": '{"intent": "RAG_REQ", "privacy_flag": false, "safe_text": "저번에 우리 손주가 언제 왔었지?", "local_action": "play_filler_hmm", "local_reply": ""}'},
        
        {"role": "user", "content": "아이고, 오늘 비가 와서 그런가 무릎이 쑤시네."},
        {"role": "assistant", "content": '{"intent": "SIMPLE_CHAT", "privacy_flag": false, "safe_text": "오늘 비가 와서 그런가 무릎이 쑤시네.", "local_action": null, "local_reply": "어머나, 비가 오니 무릎이 많이 아프시군요. 따뜻한 찜질을 해보시는 건 어떨까요? 제가 곁에서 지켜드릴게요."}'},
        
        {"role": "user", "content": "요즘 너무 외로워서 밤에 잠이 안 와."},
        {"role": "assistant", "content": '{"intent": "SIMPLE_CHAT", "privacy_flag": false, "safe_text": "요즘 너무 외로워서 밤에 잠이 안 와.", "local_action": null, "local_reply": "밤에 혼자 깨어 계시면 참 적적하시겠어요. 제가 어르신의 마음을 다 안아드릴 순 없지만, 오늘 이렇게 이야기 나눠주셔서 정말 감사해요."}'},
        
        {"role": "user", "content": raw_text}
    ]
    
    try:
        response = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.0,
            response_format={"type": "json_object"},
            timeout=10.0
        )
        
        llm_output = response.choices[0].message.content
        print(f"✅ [GX10 파싱 결과]: {llm_output}")
        
        routing_data = json.loads(llm_output)
        routing_data["acoustic_event"] = analyze_audio_level()
        return routing_data

    except Exception as e:
        print(f"❌ GX10 서버 통신 실패: {e}")
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

async def play_audio_from_url(session: aiohttp.ClientSession, audio_url: str):
    if not audio_url: return
    print(f"🔊 [Cloud Audio] 백엔드 스트리밍 재생: {audio_url}")
    await asyncio.sleep(1)

# ==========================================
# ☁️ 4. [클라우드] 백엔드 통신 모듈 (동기 & 비동기 로깅)
# ==========================================
async def dispatch_to_backend(session: aiohttp.ClientSession, routing_data: dict, raw_text: str):
    """RAG_REQ: 백엔드로 보내고 답변을 기다리는 함수"""
    final_text = routing_data["safe_text"] if routing_data.get("privacy_flag") else raw_text
    payload = {
        "text": final_text, "intent": routing_data.get("intent"),
        "privacy_flag": routing_data.get("privacy_flag"), "acoustic_event": routing_data.get("acoustic_event")
    }
    trigger_url = f"{BACKEND_URL}/api/v1/memory/ask_text/{DEPENDENT_ID}"
    
    try:
        async with session.post(trigger_url, json=payload, timeout=5) as resp:
            if resp.status != 202: return "백엔드 서버 응답 지연", None
            job_id = (await resp.json()).get("job_id")
    except Exception: return "어르신, 인터넷 연결이 잠시 끊어졌어요.", None

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
        except Exception: continue
    return "생각이 너무 오래 걸리네요. 다시 말씀해 주시겠어요?", None

async def dispatch_to_backend_async_log(session: aiohttp.ClientSession, routing_data: dict, raw_text: str):
    """SIMPLE_CHAT: 답변을 기다리지 않고 백그라운드에서 조용히 데이터만 적재"""
    final_text = routing_data["safe_text"] if routing_data.get("privacy_flag") else raw_text
    payload = {
        "text": final_text, "intent": routing_data.get("intent"),
        "privacy_flag": routing_data.get("privacy_flag"), "acoustic_event": routing_data.get("acoustic_event")
    }
    trigger_url = f"{BACKEND_URL}/api/v1/memory/ask_text/{DEPENDENT_ID}"
    
    try:
        async with session.post(trigger_url, json=payload, timeout=5) as resp:
            if resp.status == 202:
                print("📨 [Background Log] 스몰톡 & 감정 분석 데이터 백엔드 적재 완료")
    except Exception as e:
        print(f"❌ [Background Log] 백엔드 로깅 실패: {e}")

# ==========================================
# 🔀 5. 메인 웹소켓 컨트롤러 (Flask 연동 시 Blueprint/Route 포인트)
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
                    
                    routing_data = await analyze_with_gx10_llm(raw_text)
                    
                    # 💡 [핵심 라우팅] RAG vs 스몰톡 분기
                    if routing_data.get("intent") == "RAG_REQ":
                        print("☁️ [라우터] 과거 기억 탐색 필요 -> 클라우드 RAG 토스")
                        if routing_data.get("local_action"):
                            asyncio.create_task(play_local_action(routing_data.get("local_action")))
                        
                        ai_response_text, audio_url = await dispatch_to_backend(session, routing_data, raw_text)
                        
                    else:
                        print("🏠 [라우터] 단순 스몰톡/공감 -> GX10 자체 응답 사용 (딜레이 0초)")
                        ai_response_text = routing_data.get("local_reply", "네 어르신, 제가 귀 기울여 듣고 있어요.")
                        audio_url = None
                        
                        # 🌟 스몰톡 데이터 비동기 적재 (어르신 대기 시간 없음)
                        asyncio.create_task(dispatch_to_backend_async_log(session, routing_data, raw_text))

                    await websocket.send(json.dumps({
                        "status": "speaking",
                        "type": "AI_RESPONSE",
                        "text": ai_response_text
                    }))
                    
                    if audio_url:
                        await play_audio_from_url(session, audio_url)
                    
                    await websocket.send(json.dumps({"status": "idle"}))
                    
        except websockets.exceptions.ConnectionClosed:
            print("❌ [웹소켓] React와의 연결이 해제되었습니다.")

async def main():
    # 도커 환경을 위한 0.0.0.0 바인딩
    print("🚀 [Raspberry Pi Agent] ws://0.0.0.0:8765 에서 대기 중...")
    async with websockets.serve(handle_client, "0.0.0.0", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
