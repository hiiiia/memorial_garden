import asyncio
import websockets
import json
import aiohttp
import uuid
import os
import time
from config import settings
from database import db_manager 


# ==========================================
# 환경 설정 (라즈베리 파이 Docker 환경)
# ==========================================
AI_SERVER_URL = settings.AI_SERVER_URL
DEPENDENT_ID = settings.DEPENDENT_ID
BACKEND_CALLBACK_URL = settings.BACKEND_URL + "api/v1/callbacks/jobs/{job_id}/analyzing-result"
# ==========================================
# [로컬] STT 및 오디오 분석 모듈
# ==========================================
def recognize_speech_from_mic():
    print("🎙️ [하드웨어] 마이크 활성화. 어르신 말씀 듣는 중... (2초 대기)")
    time.sleep(2) 
    
    # 💡 테스트 시 시나리오에 맞게 더미 텍스트를 변경해보세요.
    dummy_text = "우리 며느리랑 돈 때문에 서운했던 게 언제였더라?" 
    
    print(f"📝 [STT 인식 완료]: {dummy_text}")
    return dummy_text

# ==========================================
#  [로컬] 오디오 재생 제어
# ==========================================
async def play_local_action(action_file: str):
    if not action_file: return
    print(f"🔊 [Local Audio] 추임새/효과음 재생 (딜레이 0초): {action_file}")
    await asyncio.sleep(0.1) 

    
    
# 전역 비동기 큐 생성
audio_task_queue = asyncio.Queue()

# ==========================================
# [소비자] Track 2: 백그라운드 워커 (무한 루프)
# ==========================================
async def background_audio_worker():
    """
    큐에 들어온 오디오 파일들을 순차적으로 AI 서버에 업로드하고 파기합니다.
    서버가 시작될 때 백그라운드에서 단 하나만 실행되어 대기합니다.
    """
    print("[Background Worker] 오디오 업로드 워커 대기 중...")
    
    while True:
        # 1. 큐에 작업이 들어올 때까지 대기
        task_data = await audio_task_queue.get()
        
        wav_path = task_data.get("wav_path")
        user_id = task_data.get("user_id")
        stt_text = task_data.get("stt_text")
        
        if not os.path.exists(wav_path):
            print(f"[Edge Worker] 오디오 파일 누락: {wav_path}")
            audio_task_queue.task_done()
            continue

        # 2. AI 서버로 업로드
        try:
            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                data.add_field('user_id', user_id)
                data.add_field('stt_text', stt_text)
                data.add_field('callback_url', BACKEND_URL) 
                data.add_field('file', open(wav_path, 'rb'), filename='input.wav', content_type='audio/wav')

                url = f"{AI_SERVER_URL}/api/v1/analyze/audio"
                
                print(f"[Edge Worker] 업로드 시작: {wav_path}")
                async with session.post(url, data=data) as resp:
                    if resp.status in (200, 202):
                        print(f"[Edge Worker] 업로드 성공: {wav_path}")
                    else:
                        print(f"[Edge Worker] 서버 업로드 실패: HTTP {resp.status}")

        except Exception as e:
            print(f"[Edge Worker] 통신 중 오류 발생: {e}")
            
        finally:
            # 3. [보안 핵심] 처리 완료 후 로컬 오디오 파기
            if os.path.exists(wav_path):
                os.remove(wav_path)
                print(f"[Edge 보안] 파일 파기 완료: {wav_path}")
            
            # 4. 큐에 작업이 완료되었음을 알림
            audio_task_queue.task_done()

# ==========================================
# [생산자] Track 1: 실시간 초저지연 라우팅 
# ==========================================
async def get_response_from_ai_server(session, raw_text: str, memory_context: str):
    url = f"{AI_SERVER_URL}/api/v1/edge/route"
    payload = {
        "user_id": DEPENDENT_ID,
        "text": raw_text,
        "memory_context": memory_context
    }
    try:
        async with session.post(url, json=payload, timeout=5.0) as resp:
            if resp.status == 200:
                return await resp.json()
    except Exception as e:
        print(f"[Edge Error] 라우팅 서버 호출 실패: {e}")
        
    return {
        "local_reply": "어르신, 제가 방금 하신 말씀을 놓쳤어요. 다시 한 번 말씀해 주시겠어요?"
    }


# ==========================================
# 메인 웹소켓 컨트롤러
# ==========================================
async def handle_client(websocket, path="/"):
    print("[웹소켓] React 프론트엔드 연결 성공!")
    async with aiohttp.ClientSession() as session:
        try:
            async_tasks = set()
            async for message in websocket:
                data = json.loads(message)
                
                if data.get("command") == "force_record":
                    await websocket.send(json.dumps({"status": "listening"}))
                    
                    # [구조 변경] 덮어쓰기 방지를 위한 고유 오디오 파일명 생성
                    unique_id = uuid.uuid4().hex[:8]
                    wav_file_path = f"audio_{unique_id}.wav"
                    
                    # 0단계: 마이크 녹음 및 파일 저장 + STT 변환
                    # (주의: 실제 마이크 제어 함수가 wav_file_path로 파일을 떨구도록 연동해야 합니다)
                    # record_to_wav(wav_file_path) 
                    raw_text = await asyncio.to_thread(recognize_speech_from_mic)
                    
                    await websocket.send(json.dumps({"status": "processing"}))
                    
                    # 1단계 [온디바이스 RAG]: 서버로 가기 전, 라즈베리 로컬 DB에서 유사 기억 파싱
                    search_results = db_manager.search_memory(raw_text, limit=1)
                    memory_context = ""
                    if search_results:
                        found_memory = search_results[0]
                        memory_context = f"어르신의 과거 기억 (날짜: {found_memory['date']}): {found_memory['content']}"
                        print("[Local RAG] 로컬 기억 매칭 확인 -> 서버 가이드로 주입")
                    
                    # 2단계 [네트워크 최적화]: 원문과 로컬 컨텍스트를 함께 AI 서버로 위임 (Track 1)
                    routing_data = await get_response_from_ai_server(session, raw_text, memory_context)
                    
                    # 3단계 [온디바이스 격리 적재]: AI 서버가 기억해야 할 사실정보라고 판정하면 로컬에 적재
                    if routing_data.get("save_flag", False):
                        db_manager.insert_memory(raw_text)
                    
                    # 4단계: 추임새 처리
                    if routing_data.get("local_action"):
                        task = asyncio.create_task(play_local_action(routing_data.get("local_action")))
                        async_tasks.add(task)
                        task.add_done_callback(async_tasks.discard)
                    
                    # 5단계: 최종 가공 답변 추출 및 프론트엔드 발화 지시
                    ai_response_text = routing_data.get("local_reply", "기억 상자를 조금 더 찾아볼게요.")
                    await websocket.send(json.dumps({
                        "status": "speaking",
                        "type": "AI_RESPONSE",
                        "text": ai_response_text
                    }))
                    
                    # 6단계 [Track 2 큐잉]: 무거운 음향 분석 및 백엔드 로깅을 백그라운드 워커로 이관
                    # 기존 dispatch_to_backend_async_log를 제거하고 큐에 작업을 밀어 넣습니다.
                    await audio_task_queue.put({
                        "wav_path": wav_file_path,
                        "user_id": DEPENDENT_ID,
                        "stt_text": raw_text
                    })
                    print(f"[Edge Queue] 백그라운드 심층 분석 대기열에 추가됨 ({wav_file_path})")
                    
                    await websocket.send(json.dumps({"status": "idle"}))

        except websockets.exceptions.ConnectionClosed:
            print("[웹소켓] 연결 해제")
    
# ==========================================
# 애플리케이션 시작점
# ==========================================
async def main():
    # 1. 백그라운드 워커를 이벤트 루프에 미리 등록하여 실행
    worker_task = asyncio.create_task(background_audio_worker())
    
    # 2. 웹소켓 서버 시작
    server = await websockets.serve(handle_client, "0.0.0.0", 8765)
    print("[Edge] 라즈베리 파이 엣지 서버 가동 시작 (포트: 8765)")
    
    await server.wait_closed()
    
    # 워커 종료 처리 (서버가 닫힐 때)
    worker_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())