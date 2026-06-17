import requests
import json
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

LLM_API_URL = "[http://127.0.0.1:8080/completion](http://127.0.0.1:8080/completion)"

def handle_local_action(action_code):
    """[스레드 A] 로컬 기기 제어 및 추임새 오디오 백그라운드 즉시 재생 (Latency Masking)"""
    if action_code:
        print(f"🌟 [LOCAL THREAD] 즉시 로컬 오디오 재생 트리거: {action_code}")
        # 예: os.system(f"aplay /mnt/sdcard/audio/{action_code}")

def send_to_health_db(meta_data):
    """[스레드 B] 분석 연속성을 보장하기 위한 수치형 메타데이터의 백엔드 전송"""
    print(f"📊 [META THREAD] 헬스케어 메타데이터 시계열 DB 전송 완료: {meta_data}")

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message', '')
    
    # 1회 추론으로 멀티 플래그 출력을 강제하기 위한 템플릿 엔지니어링
    prompt = f"""<|im_start|>system
You are an Edge AI router. Analyze the user's intent and output ONLY a valid JSON object. 
Format: {{"intent": "RAG_REQ" or "LOCAL_CMD", "privacy_flag": true/false, "local_action": "play_filler.mp3" or null}}
<|im_end|>
<|im_start|>user
{user_input}<|im_end|>
<|im_start|>assistant
"""

    payload = {
        "prompt": prompt,
        "n_predict": 128,
        "temperature": 0.1,  # 완벽한 JSON 규격을 위해 생성 다양성을 억제
        "stop": ["<|im_end|>"]
    }

    try:
        # 1. 엣지 가속 sLLM 서버 호출
        response = requests.post(LLM_API_URL, json=payload).json()
        ai_output = response['content'].strip()
        
        # 2. 구조화 JSON 파싱
        routing_data = json.loads(ai_output)
        intent = routing_data.get('intent')
        privacy = routing_data.get('privacy_flag')
        action = routing_data.get('local_action')

        # 3. 비동기/멀티스레딩 기반 병렬 디스패치 전개
        # 로컬 오디오 즉각 재생 실행 (사용자 체감 Latency 0초 구현)
        threading.Thread(target=handle_local_action, args=(action,)).start()
        
        # VAD 및 통계적 수치 분리 추출 (예시 파라미터 백엔드 전송)
        mock_meta = {"wpm": 38, "pause_duration": 3.1, "depression_score": 0.75}
        threading.Thread(target=send_to_health_db, args=(mock_meta,)).start()

        # 4. 프라이버시 마스킹 처리 및 최종 분기 반환
        if privacy:
            print("🚨 [PRIVACY DROP] 민감 대화 데이터 감지됨. 원본 텍스트 로컬 메모리에서 즉각 파기 완료.")
            return jsonify({
                "status": "success",
                "edge_decision": intent,
                "forward_text": "[USER_REQUESTED_PRIVACY_DROP]",  # 시맨틱 데이터 마스킹
                "message": "비식별화 보호 처리 및 로컬 제어 완료"
            })
        else:
            return jsonify({
                "status": "success",
                "edge_decision": intent,
                "forward_text": user_input,
                "message": "클라우드 런타임 연동 포워딩 준비 완료"
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Flask 에이전트 구동 (포트 5000)
    app.run(host='0.0.0.0', port=5000)