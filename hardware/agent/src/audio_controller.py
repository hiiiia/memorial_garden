import asyncio
import websockets
import json
import threading
import time
import speech_recognition as sr
import requests # API 통신용

# ==========================================
# 1. 전역 상태 및 이벤트 관리
# ==========================================
WAKE_WORD = "손주야"
BACKEND_UPLOAD_URL = "http://backend:8000/api/audio/upload" # docker-compose 내부망 주소
connected_react_clients = set()
force_record_event = threading.Event()

# ==========================================
# 2. 로컬 웹소켓 서버 (React UI 양방향 통신)
# ==========================================
def send_status_to_react(status_msg):
    """React로 상태('idle', 'listening', 'processing') 푸시"""
    async def notify():
        if connected_react_clients:
            message = json.dumps({"status": status_msg})
            await asyncio.gather(*(client.send(message) for client in connected_react_clients))
            print(f"📡 [UI 업데이트] {status_msg}")
    
    try:
        loop = asyncio.get_event_loop()
        asyncio.run_coroutine_threadsafe(notify(), loop)
    except Exception:
        pass

async def local_websocket_handler(websocket):
    print("✅ React UI가 내부 웹소켓에 연결되었습니다!")
    connected_react_clients.add(websocket)
    try:
        async for message in websocket:
            data = json.loads(message)
            if data.get("command") == "force_record":
                print("\n🔘 [화면 터치] 강제 녹음 명령 수신!")
                force_record_event.set()
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_react_clients.remove(websocket)
        print("❌ React UI 연결 해제")

def start_local_websocket_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    start_server = websockets.serve(local_websocket_handler, "0.0.0.0", 8765)
    loop.run_until_complete(start_server)
    loop.run_forever()

# ==========================================
# 3. 백엔드 통신 로직
# ==========================================
def upload_to_backend(audio_data):
    """녹음된 오디오를 WAV로 변환 후 FastAPI 백엔드로 전송"""
    print("🚀 백엔드 서버로 파일 전송 시작...")
    try:
        # 오디오 데이터를 WAV 바이너리로 변환
        wav_data = audio_data.get_wav_data()
        
        # multipart/form-data 형식으로 전송
        files = {
            "audio_file": ("record.wav", wav_data, "audio/wav")
        }
        data = {
            "user_id": "USER_ABC",
            "device_id": "rpi5_master_01"
        }
        
        # FastAPI 서버로 POST 요청 (타임아웃 10초 설정)
        response = requests.post(BACKEND_UPLOAD_URL, files=files, data=data, timeout=10)
        
        if response.status_code == 201:
            print(f"✅ 백엔드 전송 성공! (JobID: {response.json().get('data', {}).get('job_id')})")
        else:
            print(f"⚠️ 전송 실패: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ 네트워크 에러 발생: {e}")

# ==========================================
# 4. 음성 인식 제어 루프
# ==========================================
def run_audio_controller():
    recognizer = sr.Recognizer()
    
    with sr.Microphone() as source:
        print("\n[주변 소음 적응 중...]")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        
        while True:
            send_status_to_react("idle")
            
            if force_record_event.is_set():
                force_record_event.clear()
            else:
                try:
                    # 1초 단위로 호출어 대기
                    audio_check = recognizer.listen(source, timeout=1, phrase_time_limit=3)
                    text = recognizer.recognize_google(audio_check, language="ko-KR")
                    if WAKE_WORD not in text:
                        continue
                except sr.WaitTimeoutError:
                    continue
                except Exception:
                    continue

            # 호출어 인식 or 터치 발생 시 실행
            print("👂 어르신 말씀 듣는 중...")
            send_status_to_react("listening")
            
            try:
                # 최대 10초 녹음
                record_audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                print("⏳ [녹음 완료] 데이터 처리 중...")
                send_status_to_react("processing")
                
                # 백엔드 업로드 실행
                upload_to_backend(record_audio)
                
                # 업로드 후에는 백엔드가 React로 직접 응답(TTS)을 쏠 때까지 파이썬은 다시 대기
                
            except sr.WaitTimeoutError:
                print("입력이 없어 대기 상태로 돌아갑니다.")
            except Exception as e:
                print(f"녹음 중 오류: {e}")

if __name__ == "__main__":
    # 로컬 웹소켓 서버를 백그라운드 스레드로 실행
    ws_thread = threading.Thread(target=start_local_websocket_server, daemon=True)
    ws_thread.start()
    
    time.sleep(1)
    print("=======================================")
    print("   🎙️ Audio Controller 구동 시작   ")
    print("=======================================")
    run_audio_controller()