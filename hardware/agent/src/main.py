import asyncio
import websockets
import json
import aiohttp
import uuid
import os
import time
from config import settings
from database import db_manager 
import sounddevice as sd
import soundfile as sf
import numpy as np
import shutil


TEST_MODE = True 
TEST_INPUT_FILE = "test_1.mp3"  # 실제 테스트용 파일 경로 (미리 준비 필요)
TEST_INPUT_TEXT = "오늘 날씨가 너무 좋아서 동네 뒷산에 산책을 다녀왔어. 옛날에 우리 영수 어릴때 같이 손잡고 올라가던 기억이 나서, 기분이 참 좋더라구"

# ==========================================
# 환경 설정 (라즈베리 파이 Docker 환경)
# ==========================================
AI_SERVER_URL = settings.AI_SERVER_URL
DEPENDENT_ID = settings.DEPENDENT_ID
BASE_DIR = "/app/data"
# ==========================================
# [로컬] STT 및 오디오 분석 모듈
# ==========================================
def recognize_speech_from_mic():
    if TEST_MODE:
        print(f"📝 [TEST] STT 모킹 작동. 고정 텍스트 반환...")
        return TEST_INPUT_TEXT
    
    # 실제 하드웨어 로직 (기존 코드)
    print("🎙️ [하드웨어] 마이크 활성화. 어르신 말씀 듣는 중...")
    time.sleep(2) 
    return "실제 음성 데이터 처리 로직"

# ==========================================
#  [로컬] 오디오 재생 제어
# ==========================================
async def play_local_action(action_file: str):
    if not action_file: return
    print(f"🔊 [Local Audio] 추임새/효과음 재생 (딜레이 0초): {action_file}")
    await asyncio.sleep(0.1) 

# ==========================================
# [테스트 모드] 오디오 녹음 제어 (AudioRecorder)
# ==========================================
class AudioRecorder:
    def __init__(self):
        self.is_recording = False
        self.frames = []
        self.stream = None
        self.fs = 16000

    def start_recording(self):
        if TEST_MODE:
            print(f"[TEST] 녹음 시작 (시뮬레이션)")
            self.is_recording = True
            return

        self.frames = []
        self.is_recording = True
        self.stream = sd.InputStream(samplerate=self.fs, channels=1, callback=self.callback)
        self.stream.start()
        print("[Edge] 녹음 시작됨...")

    def stop_recording(self, wav_name):
        self.is_recording = False
        full_path = os.path.join(BASE_DIR, wav_name)
        if TEST_MODE:
            # 1. 파일 존재 여부 확인
            test_source = os.path.join(BASE_DIR, TEST_INPUT_FILE)
            if os.path.exists(test_source):
                print(f"[TEST] 녹음 정지. {TEST_INPUT_FILE} 복사 시작 -> {full_path}")
                shutil.copy(test_source, full_path) # mp3를 지정된 wav_path로 복사
                return True, full_path
            else:
                print(f"[TEST ERROR] 테스트 파일 없음: {TEST_INPUT_FILE}")
                return False, None

        # 실제 하드웨어 로직
        if self.stream:
            self.stream.stop()
            self.stream.close()
        
        if self.frames:
            recording = np.concatenate(self.frames, axis=0)
            sf.write(full_path, recording, self.fs)
            print(f"[Edge] 녹음 종료 및 저장 완료: {full_path}")
            return True, full_path
        return False, None

    def callback(self, indata, frames, time, status):
        if self.is_recording:
            self.frames.append(indata.copy())

# 전역 객체 생성
recorder = AudioRecorder()

    
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
# 5. 메인 웹소켓 컨트롤러 (강화 버전)
# ==========================================
async def handle_client(websocket, path="/"):
    print("[웹소켓] React 프론트엔드 연결 성공!")
    async with aiohttp.ClientSession() as session:
        try:
            async_tasks = set()
            async for message in websocket:
                data = json.loads(message)
                
                if data.get("command") == "force_record":
                    if not recorder.is_recording:
                        recorder.start_recording()
                        await websocket.send(json.dumps({"status": "listening"}))
                    else:
                        unique_id = uuid.uuid4().hex[:8]
                        wav_file_path = f"audio_{unique_id}.wav"
                        success, wav_file_path = recorder.stop_recording(wav_file_path)
                    
                        if success:
                            # [안전장치] 전체 프로세스를 try-except로 감싸서 UI가 멈추지 않게 함
                            try:
                                await websocket.send(json.dumps({"status": "processing"}))
                                
                                raw_text = await asyncio.to_thread(recognize_speech_from_mic)
                                
                                search_results = db_manager.search_memory(raw_text, limit=1)
                                memory_context = ""
                                if search_results:
                                    found_memory = search_results[0]
                                    memory_context = f"어르신의 과거 기억 (날짜: {found_memory['date']}): {found_memory['content']}"
                                
                                routing_data = await get_response_from_ai_server(session, raw_text, memory_context)
                                
                                if routing_data.get("save_flag", False):
                                    db_manager.insert_memory(raw_text)
                                
                                if routing_data.get("local_action"):
                                    task = asyncio.create_task(play_local_action(routing_data.get("local_action")))
                                    async_tasks.add(task)
                                    task.add_done_callback(async_tasks.discard)
                                
                                ai_response_text = routing_data.get("local_reply", "기억 상자를 조금 더 찾아볼게요.")
                                await websocket.send(json.dumps({
                                    "status": "speaking",
                                    "type": "AI_RESPONSE",
                                    "text": ai_response_text
                                }))
                                
                                await audio_task_queue.put({
                                    "wav_path": wav_file_path,
                                    "user_id": DEPENDENT_ID,
                                    "stt_text": raw_text
                                })
                                
                            except Exception as e:
                                print(f"[Edge 프로세스 에러]: {e}")
                                await websocket.send(json.dumps({"status": "error", "message": "분석 중 오류 발생"}))
                            finally:
                                # 어떤 상황에서도 UI 상태는 idle로 복구
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