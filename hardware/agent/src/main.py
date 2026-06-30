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

### 도커 환경에서는 계속 변경됨.
# # ==========================================
# # 기기의 고유 MAC 주소를 가져오는 함수
# # ==========================================
# def get_mac_address():
#     mac_num = hex(uuid.getnode()).replace('0x', '').upper()
#     mac = '-'.join(mac_num[i: i + 2] for i in range(0, 11, 2))
#     return mac
# # MAC 주소를 전역 변수로 세팅
# HW_MAC_ADDRESS = get_mac_address()

HW_MAC_ADDRESS = settings.RASPI_MAC
# ==========================================
# 환경 설정 (라즈베리 파이 Docker 환경)
# ==========================================
AI_SERVER_URL = settings.AI_SERVER_URL
DEPENDENT_ID = settings.DEPENDENT_ID
DEPENDENT_NAME = None
DEVICE_HW_KEY = settings.HW_TOKEN
DEVICE_AI_KEY = settings.AI_TOKEN
BASE_DIR = "/app/data"

BACKEND_URL = settings.BACKEND_URL
DEVICE_TOKEN = None

class InitData:
    init_data = {}
    ready_event = asyncio.Event()

active_frontend_ws = None

# ==========================================
# React가 클라우드로 보낼 메시지를 담아둘 우체통(Queue)
# ==========================================
cloud_outbound_queue = asyncio.Queue()

# ==========================================
# 부팅 시 자동 등록 및 인증 통합 함수
# ==========================================
async def boot_and_authenticate():
    """부팅 시 MAC 주소와 HW_SECRET_KEY 기반으로 서버에 등록하고 JWT 토큰을 발급받음"""
    global DEPENDENT_ID, DEPENDENT_NAME, DEVICE_TOKEN, DEVICE_HW_KEY
    
    # 환경변수에서 하드웨어 시크릿 키 로드 (없으면 진행 불가)
    # (앞서 .env에 설정한 변수명에 맞게 "DEVICE_HW_KEY" 사용)
    if not DEVICE_HW_KEY:
        print("❌ 에러: .env 파일에 DEVICE_HW_KEY(하드웨어 보안 키)이 설정되지 않았습니다.")
        return False
        
    url = f"{BACKEND_URL}/api/v1/dependent/device/register"
    
    # 기본 정보 셋팅 (이후에 보호자 앱에서 변경 가능)
    payload = {
        "hw_id": HW_MAC_ADDRESS,
        "username": os.getenv("DEPENDENT_USERNAME", f"Ayo"),
        "name": os.getenv("DEPENDENT_NAME", "로봇 어르신"),
        "age": int(os.getenv("DEPENDENT_AGE", 75))
    }
    
    #  백엔드의 HTTPBearer(validate_hw_key)가 인식할 수 있도록 헤더 구성
    headers = {
        "Authorization": f"Bearer {DEVICE_HW_KEY}"
    }
    
    print(f"📡 백엔드 서버와 통신 중... (MAC: {HW_MAC_ADDRESS})")
    async with aiohttp.ClientSession() as session:
        try:
            # post 요청 시 headers 옵션 추가
            async with session.post(url, json=payload, headers=headers, timeout=5) as response:
                res_json = await response.json()
                
                print(f"🛠️ 백엔드 응답 데이터: {res_json}")
                
                # HTTP 상태 코드로만 성공 판단
                if response.status in [200, 201]:
                    auth_data = res_json.get("data") or {} 
                    
                    DEVICE_TOKEN = auth_data.get("access_token")
                    DEPENDENT_ID = auth_data.get("dependent_id")
                    DEPENDENT_NAME = payload["name"]
                    
                    if DEVICE_TOKEN and DEPENDENT_ID:
                        print(f"✅ 기기 셋업 완료! [보안 승인 및 JWT 토큰 발급 성공]")
                        return True
                    else:
                        print("❌ 성공 응답을 받았지만, 데이터(Token/ID)가 누락되었습니다.")
                        return False
                else:
                    error_msg = res_json.get('detail', res_json.get('message', '알 수 없는 서버 에러'))
                    print(f"❌ 기기 셋업 실패 (HTTP {response.status}): {error_msg}")
                    return False
        except Exception as e:
            print(f"❌ 서버 연결 에러: {e}")
            return False


# ==========================================
# [수정] 클라우드 백엔드 웹소켓 클라이언트 (양방향 송수신)
# ==========================================
async def cloud_websocket_client():
    ws_base = BACKEND_URL.replace("http://", "ws://").replace("https://", "wss://")
    cloud_ws_url = f"{ws_base}/ws/device/{DEPENDENT_ID}"
    
    global DEVICE_TOKEN
    
    headers = {
        "Authorization": f"Bearer {DEVICE_TOKEN}"
    }
    
    while True:
        try:
            print(f"[클라우드 WS] 백엔드({cloud_ws_url})에 연결 시도 중...")
            async with websockets.connect(cloud_ws_url, extra_headers=headers) as cloud_ws:
                print("✅ [클라우드 WS] 백엔드 웹소켓 연결 성공!")
                
                # 1. 수신 루프 (클라우드 ➔ React)
                async def receive_from_cloud():
                    global active_frontend_ws
                    async for message in cloud_ws:
                        data = json.loads(message)
                        print(f"📥 [클라우드 ➔ HW]: {data}")
                        
                        if data.get('action') == "INIT_SETTINGS":
                            print(f"📥 [클라우드 ➔ HW]: 초기 데이터 저장완료")
                            
                            InitData.init_data = data['data']
                            print(f"📥 [클라우드 ➔ HW]: 초기 데이터 저장완료")
                            
                            # 이벤트 트리거
                            InitData.ready_event.set()
                        
                        if active_frontend_ws is not None:
                            await active_frontend_ws.send(message) # React로 그대로 전달
                # 2. 송신 루프 (React ➔ 우체통 ➔ 클라우드)
                async def send_to_cloud():
                    while True:
                        # 큐에 데이터가 들어올 때까지 대기하다가 들어오면 빼냄
                        outbound_msg = await cloud_outbound_queue.get()
                        await cloud_ws.send(json.dumps(outbound_msg))
                        print(f"📤 [HW ➔ 클라우드] 전송 완료: {outbound_msg}")
                        cloud_outbound_queue.task_done()

                # 두 루프를 동시에 실행 (둘 중 하나라도 끊어지면 예외 발생하여 재연결 루프로 감)
                await asyncio.gather(receive_from_cloud(), send_to_cloud())
                        
        except Exception as e:
            print(f"❌ [클라우드 WS] 연결 끊김 또는 에러 발생: {e}. 5초 후 재연결...")
            await asyncio.sleep(5)


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
    global DEVICE_AI_KEY
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

        # 2. AI 서버로 업로드 (인증 헤더 추가)
        try:
            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                data.add_field('user_id', user_id)
                data.add_field('stt_text', stt_text)
                data.add_field('file', open(wav_path, 'rb'), filename='input.wav', content_type='audio/wav')

                url = f"{AI_SERVER_URL}/api/v1/analyze/audio"
                
                # 인증 헤더 세팅
                headers = {
                    "Authorization": f"Bearer {DEVICE_AI_KEY}"
                }
                
                print(f"[Edge Worker] 업로드 시작: {wav_path}")
                
                async with session.post(url, data=data, headers=headers) as resp:
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
    global DEVICE_AI_KEY
    
    url = f"{AI_SERVER_URL}/api/v1/edge/route"
    payload = {
        "user_id": DEPENDENT_ID,
        "text": raw_text,
        "memory_context": memory_context
    }
    
    # 인증 헤더 세팅
    headers = {
        "Authorization": f"Bearer {DEVICE_AI_KEY}"
    }
    
    try:
        async with session.post(url, json=payload, headers=headers, timeout=5.0) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                print(f"[Edge Error] 비정상 응답: HTTP {resp.status}")
    except Exception as e:
        print(f"[Edge Error] 라우팅 서버 호출 실패: {e}")
        
    return {
        "local_reply": "어르신, 제가 방금 하신 말씀을 놓쳤어요. 다시 한 번 말씀해 주시겠어요?"
    }

# ==========================================
# 5. 메인 웹소켓 컨트롤러 (강화 버전)
# ==========================================
async def handle_client(websocket, path="/"):
    global active_frontend_ws
    active_frontend_ws = websocket
    print("✅ [로컬 WS] React 프론트엔드 연결 성공!")
    
    print("[로컬 WS] React 프론트엔드 세팅값 수신 대기중")
    await InitData.ready_event.wait()
    payload = {
        "action": "INIT_SETTINGS",
        "data": InitData.init_data  # 딕셔너리 객체 자체를 전달
    }
    
    await websocket.send(json.dumps(payload))
    print(f"✅ [로컬 WS] React 프론트엔드 초기 세팅 전송값 완료! : {InitData.init_data}")
    
    async with aiohttp.ClientSession() as session:
        try:
            async_tasks = set()
            async for message in websocket:
                data = json.loads(message)
                
                # 1. 로컬 하드웨어 제어 명령
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

                # 2. 프론트엔드가 클라우드(백엔드)로 보내려는 상태나 응답인 경우
                elif data.get("target") == "cloud":
                    print(f"[React ➔ HW] 클라우드 전송 요청 수신: {data}")
                    # 수신한 데이터를 즉시 우체통(Queue)에 넣어서 send_to_cloud()가 가져가게 함
                    await cloud_outbound_queue.put(data.get("payload"))
                
                # 3. 연결 설정시 device token을 react에 전달
                elif data.get("command") == "get_token":
                    await websocket.send(json.dumps({"token": f"{DEVICE_TOKEN}",
                                                     "HW_MAC" : f"{HW_MAC_ADDRESS}",
                                                     }))
                    
                    print(f"[React에 토큰 전달 완료]: {DEVICE_TOKEN}")
                else :
                    print(f"[ETC]")
        
        
        except websockets.exceptions.ConnectionClosed:
            print("[웹소켓] 연결 해제")
            
        finally:
            if active_frontend_ws == websocket:
                active_frontend_ws = None
        
    
# ==========================================
# 애플리케이션 시작점
# ==========================================
async def main():
    
    is_authenticated = await boot_and_authenticate()
    
    if not is_authenticated:
        print("⚠️ 기기 인증 실패. 시스템 대기 모드로 진입합니다.")
        return
    
    # 1. 백그라운드 오디오 워커 실행 (기존)
    worker_task = asyncio.create_task(background_audio_worker())
    
    # ==========================================================
    # 2. 클라우드 백엔드 통신용 웹소켓 클라이언트 백그라운드 실행
    # ==========================================================
    cloud_ws_task = asyncio.create_task(cloud_websocket_client())
    
    # 3. 로컬 프론트엔드(React) 통신용 웹소켓 서버 시작 (기존)
    server = await websockets.serve(handle_client, "0.0.0.0", 8765)
    print("[Edge] 라즈베리 파이 엣지 서버 가동 시작 (포트: 8765)")
    
    await server.wait_closed()
    
    # 종료 처리 (서버가 닫힐 때)
    worker_task.cancel()
    cloud_ws_task.cancel()  # 클라우드 웹소켓 태스크도 함께 종료되도록 추가

if __name__ == "__main__":
    asyncio.run(main())