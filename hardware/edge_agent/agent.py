import asyncio
import websockets
import json
import aiohttp
import os
import time

# ==========================================
# 🔗 환경 설정 (네이티브 베어메탈 환경에 맞춤)
# ==========================================
BACKEND_URL = os.getenv("BACKEND_URL", "http://192.168.1.82:8000") 
# 도커 네트워크 대신 젯슨 나노의 로컬호스트 주소 사용
LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL", "http://127.0.0.1:8080/v1/chat/completions")
DEPENDENT_ID = "dep_003" 

# ==========================================
# 🎤 1. [로컬] STT 및 오디오 분석 모듈
# ==========================================
def recognize_speech_from_mic():
    print("🎙️ [하드웨어] 마이크 활성화. 어르신 말씀 듣는 중... (2초 대기)")
    time.sleep(2) # 실제 STT 인식 대기 시간 시뮬레이션
    
    # 💡 테스트를 위해 아래 두 문장 중 하나를 주석 해제하여 번갈아 써보세요.
    # dummy_text = "거실 불 좀 켜줄래?" # -> LOCAL_CMD 분기 테스트용
    dummy_text = "아까 며느리 흉본 거는 비밀로 해줘. 지워버려." # -> RAG_REQ + 프라이버시 분기 테스트용
    
    print(f"📝 [STT 인식 완료]: {dummy_text}")
    return dummy_text

def analyze_audio_level():
    # 💡 개발자님이 직접 RMS/VAD 로직을 구현하세요.
    return "silence"

# ==========================================
# 🧠 2. [로컬] 엣지 Qwen 0.5B 라우터 (Few-Shot 적용)
# ==========================================
async def analyze_with_local_llm(session: aiohttp.ClientSession, raw_text: str):
    print("🧠 [Local LLM] Qwen 0.5B 라우팅 판단 시작...")
    
    if not raw_text.strip():
        return {
            "intent": "CHAT", "privacy_flag": False, "safe_text": "", 
            "local_action": "filler_hmm.mp3", "acoustic_event": analyze_audio_level()
        }

    # 0.5B 모델의 포맷 붕괴를 막기 위한 퓨샷(Few-shot) 가이드라인 주입
    payload = {
        "messages": [
            {
                "role": "system", 
                "content": "당신은 독거노인의 일상을 나누는 반려 로봇 '기억정원'의 라우터입니다. 사용자의 말에 과거의 기억, 특정 인물, 일정 확인이 필요하면 intent를 'RAG_REQ'로 하고 local_reply를 비우세요. 하지만 단순한 인사, 날씨 이야기, 감정 표현(아프다, 우울하다 등)처럼 가벼운 스몰톡이라면 intent를 'SIMPLE_CHAT'으로 하고, 어르신에게 공감하는 다정하고 짧은 대답(해요체)을 local_reply에 작성하세요. '비밀', '지워' 같은 말이 있으면 privacy_flag를 true로 하세요."
            },
            # --- 퓨샷 1: 과거 기억 검색 (클라우드 RAG행) ---
            {
                "role": "user", "content": "저번에 우리 손주가 언제 왔었지?"
            },
            {
                "role": "assistant", "content": '{"intent": "RAG_REQ", "privacy_flag": false, "safe_text": "저번에 우리 손주가 언제 왔었지?", "local_action": "play_filler_hmm", "local_reply": ""}'
            },
            # --- 퓨샷 2: 단순 스몰톡/공감 (로컬 자체 처리) ---
            {
                "role": "user", "content": "아이고, 오늘 비가 와서 그런가 무릎이 쑤시네."
            },
            {
                "role": "assistant", "content": '{"intent": "SIMPLE_CHAT", "privacy_flag": false, "safe_text": "오늘 비가 와서 그런가 무릎이 쑤시네.", "local_action": null, "local_reply": "어머나, 비가 와서 무릎이 아프시군요. 따뜻하게 찜질을 해보시는 건 어떨까요?"}'
            },
            # --- 퓨샷 3: 프라이버시 보호 (클라우드 RAG행) ---
            {
                "role": "user", "content": "아까 며느리 흉본 건 지워줘. 남들 알면 안 돼."
            },
            {
                "role": "assistant", "content": '{"intent": "RAG_REQ", "privacy_flag": true, "safe_text": "[사용자 발화 보안 파기됨]", "local_action": "play_filler_ok", "local_reply": ""}'
            },
            # --- 실제 사용자 입력 ---
            {
                "role": "user", "content": raw_text
            }
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"} 
    }

    try:
        async with session.post(LOCAL_LLM_URL, json=payload) as resp:
            if resp.status == 200:
                result = await resp.json()
                llm_output = result["choices"][0]["message"]["content"]
                print(f"✅ [LLM 파싱 결과]: {llm_output}")
                
                routing_data = json.loads(llm_output)
                routing_data["acoustic_event"] = analyze_audio_level()
                return routing_data
            else:
                print(f"❌ 로컬 LLM 상태 에러 (Status: {resp.status})")
    except Exception as e:
        print(f"❌ 로컬 LLM 통신 실패: {e}")

    # 서버 연결 실패 시 Fallback (안전망)
    return {
        "intent": "RAG_REQ", "privacy_flag": False, "safe_text": raw_text,
        "local_action": None, "acoustic_event": None
    }

# ==========================================
# 🔊 3. [로컬] 즉각 호응음/액션 처리
# ==========================================
async def play_local_action(action_file: str):
    if not action_file: return
    print(f"🔊 [Local Action] 엣지 자체 실행 (딜레이 0초): {action_file}")
    await asyncio.sleep(0.1) 

# ==========================================
# ☁️ 4. [클라우드] 백엔드 RAG 전송 및 폴링 (비동기)
# ==========================================
async def dispatch_to_backend(session: aiohttp.ClientSession, routing_data: dict, raw_text: str):
    # 프라이버시 플래그 적용 (True일 경우 원본 파기, 요약문 전송)
    final_text = routing_data["safe_text"] if routing_data.get("privacy_flag") else raw_text
    
    payload = {
        "text": final_text,
        "intent": routing_data.get("intent"),
        "privacy_flag": routing_data.get("privacy_flag"),
        "acoustic_event": routing_data.get("acoustic_event")
    }

    trigger_url = f"{BACKEND_URL}/api/v1/memory/ask_text/{DEPENDENT_ID}"
    print(f"☁️ [Cloud RAG] 백엔드 지식망 연동 시작 (전송 텍스트: {final_text})")
    
    try:
        async with session.post(trigger_url, json=payload) as resp:
            if resp.status != 202: 
                return "백엔드 서버 응답 지연", None
            job_id = (await resp.json()).get("job_id")
    except Exception:
        return "어르신, 인터넷 연결이 잠시 끊어졌어요.", None

    status_url = f"{BACKEND_URL}/api/v1/memory/check_status/{job_id}"
    for _ in range(30): # 최대 15초 폴링 대기
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
            
    return "생각이 너무 오래 걸리네요. 다시 말씀해 주시겠어요?", None

async def play_audio_from_url(session: aiohttp.ClientSession, audio_url: str):
    if not audio_url: return
    print(f"🔊 [Cloud Audio] 백엔드 스트리밍 재생: {audio_url}")
    await asyncio.sleep(1)

# ==========================================
# 🔀 5. 메인 웹소켓 컨트롤러 (상태 및 라우팅 지휘)
# ==========================================
async def handle_client(websocket):
    print("✅ [웹소켓] React 프론트엔드 연결 성공!")
    async with aiohttp.ClientSession() as session:
        try:
            async for message in websocket:
                data = json.loads(message)
                
                # 프론트엔드에서 녹음 트리거가 들어왔을 때
                if data.get("command") == "force_record":
                    
                    # 1. 듣기 상태 (UI 업데이트)
                    await websocket.send(json.dumps({"status": "listening"}))
                    raw_text = await asyncio.to_thread(recognize_speech_from_mic)
                    
                    # 1. 처리 상태 (UI 업데이트) 및 라우팅 판단
                    await websocket.send(json.dumps({"status": "processing"}))
                    routing_data = await analyze_with_local_llm(session, raw_text)
                    
                    # 💡 [핵심 분기망] 기억 검색(RAG) vs 단순 스몰톡(Local)
                    if routing_data.get("intent") == "RAG_REQ":
                        print("☁️ [라우터] 과거 기억이나 외부 지식이 필요합니다. 클라우드 RAG 서버로 토스합니다.")
                        
                        # 딜레이 은닉용 로컬 추임새 즉시 재생
                        if routing_data.get("local_action"):
                            asyncio.create_task(play_local_action(routing_data.get("local_action")))
                        
                        # 백엔드에 RAG 질의 후 응답 대기
                        ai_response_text, audio_url = await dispatch_to_backend(session, routing_data, raw_text)
                        
                    else:
                        print("🏠 [라우터] 단순 스몰톡/공감 대화입니다. 엣지(Jetson) 단독으로 즉각 대답합니다.")
                        
                        # 🌟 0.5B 모델이 즉석에서 만들어낸 다정한 공감 문구 사용
                        ai_response_text = routing_data.get("local_reply", "네 어르신, 제가 귀 기울여 듣고 있어요.")
                        audio_url = None
                        # (단순 스몰톡이므로 딜레이 은닉용 추임새 재생 생략 가능)

                    # 3. 말하기 상태 (UI 업데이트 및 답변 텍스트 렌더링)
                    await websocket.send(json.dumps({
                        "status": "speaking",
                        "type": "AI_RESPONSE",
                        "text": ai_response_text
                    }))
                    
                    if audio_url:
                        await play_audio_from_url(session, audio_url)
                    
                    # 4. 모든 프로세스 종료 후 대기 상태 복귀
                    await websocket.send(json.dumps({"status": "idle"}))
                    
        except websockets.exceptions.ConnectionClosed:
            print("❌ [웹소켓] React와의 연결이 해제되었습니다.")

async def main():
    # React와 통신할 8765번 웹소켓 서버 포트 개방
    print("🚀 [Jetson Edge Agent] ws://0.0.0.0:8765 에서 대기 중...")
    async with websockets.serve(handle_client, "0.0.0.0", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())