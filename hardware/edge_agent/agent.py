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
                "content": "당신은 텍스트를 분석하여 JSON 형태로만 반환하는 라우터입니다. 사용자의 말에 '비밀로 해', '지워' 등의 내용이 있다면 privacy_flag를 true로 설정하고, safe_text에는 구체적 인물/사건을 가린 '[발화 삭제 요청]' 이라고 적으세요. 반드시 지정된 JSON 형식만 출력하세요."
            },
            {"role": "user", "content": "어제 우리 아들이 돈 빌려달라고 한 건 비밀이야."},
            {"role": "assistant", "content": '{"intent": "RAG_REQ", "privacy_flag": true, "safe_text": "[사용자 발화 보안 파기됨]", "local_action": "play_filler.mp3"}'},
            {"role": "user", "content": "지금 몇 시야?"},
            {"role": "assistant", "content": '{"intent": "LOCAL_CMD", "privacy_flag": false, "safe_text": "지금 몇 시야?", "local_action": "check_time"}'},
            {"role": "user", "content": raw_text}
        ],
        "temperature": 0.0, # 창의성 0% (고정 출력 유도)
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
                    
                    # 2. 처리 상태 (UI 업데이트) 및 라우팅 판단
                    await websocket.send(json.dumps({"status": "processing"}))
                    routing_data = await analyze_with_local_llm(session, raw_text)
                    
                    # 💡 [핵심 분기망] RAG 연동 vs 엣지 자체 처리
                    if routing_data.get("intent") == "RAG_REQ":
                        print("🔀 [라우터] 외부 지식/장문 대화가 필요하여 클라우드로 분기합니다.")
                        
                        # 지연 시간(Latency) 은닉용 로컬 액션 즉시 백그라운드 가동
                        if routing_data.get("local_action"):
                            asyncio.create_task(play_local_action(routing_data["local_action"]))
                        
                        # 백엔드 RAG 질의 후 응답 대기
                        ai_response_text, audio_url = await dispatch_to_backend(session, routing_data, raw_text)
                        
                    else:
                        print("🔀 [라우터] 단순 제어 명령이므로 엣지(Jetson) 단독으로 처리합니다.")
                        
                        # 외부로 나가지 않고 내부 스크립트만 실행
                        if routing_data.get("local_action"):
                            await play_local_action(routing_data["local_action"])
                            
                        # 가벼운 로컬용 자체 응답 생성
                        ai_response_text = "네 어르신, 원하시는 대로 기기를 조절했어요."
                        audio_url = None

                    # 3. 말하기 상태 (UI 업데이트 및 답변 텍스트 렌더링)
                    await websocket.send(json.dumps({
                        "status": "speaking",
                        "type": "AI_RESPONSE",
                        "text": ai_response_text
                    }))
                    
                    # 4. 클라우드에서 만들어준 음성 재생 (있는 경우)
                    if audio_url:
                        await play_audio_from_url(session, audio_url)
                    
                    # 5. 모든 프로세스 종료 후 대기 상태 복귀
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