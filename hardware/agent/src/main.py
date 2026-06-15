import asyncio
import websockets
import json
import aiohttp # ⚡ 비동기 통신을 위해 사용

# 1. 가벼운 분류기
def should_query_backend(text: str) -> bool:
    keywords = ["기억", "지난번", "언제", "했던", "그때", "이름", "가족", "어제", "저번"]
    return any(keyword in text for keyword in keywords)

# 2. 통합된 메인 핸들러
async def handle_client(websocket, path):
    print("✅ 프론트엔드(React) 웹소켓 연결 성공!")
    
    # 비동기 HTTP 세션 생성 (매번 새로 만들지 않고 유지)
    async with aiohttp.ClientSession() as session:
        try:
            async for message in websocket:
                data = json.loads(message)
                if data.get("command") == "force_record":
                    print("🎤 [명령 수신] 어르신이 마이크 버튼을 눌렀습니다.")
                    
                    # 1단계: 듣는 중
                    await websocket.send(json.dumps({"status": "listening"}))
                    await asyncio.sleep(2) # STT 처리 시뮬레이션
                    
                    user_text = "지난번 우리 손주 이름이 뭐였지?" # 실제로는 STT 결과값
                    print(f"📝 인식된 텍스트: {user_text}")
                    
                    # 2단계: 처리 중 (라우팅 로직)
                    await websocket.send(json.dumps({"status": "processing"}))
                    
                    if should_query_backend(user_text):
                        print("🌐 [Router] 백엔드 RAG 서버로 조회 요청")
                        async with session.post("http://your-backend-url/query", json={"text": user_text}) as resp:
                            result = await resp.json()
                            ai_response = result.get("answer", "기억을 찾는 중 오류가 발생했어요.")
                    else:
                        print("⚡ [Router] 로컬 즉시 응답 생성")
                        ai_response = "네, 손주분은 철수님이라고 하셨었죠!"
                    
                    print("✅ AI 응답 생성 완료")

                    # 3단계: 말하는 중
                    await websocket.send(json.dumps({
                        "status": "speaking",
                        "type": "AI_RESPONSE",
                        "text": ai_response
                    }))
                    await asyncio.sleep(3) # TTS 재생 시간 대기
                    
                    # 4단계: 대기 복귀
                    await websocket.send(json.dumps({"status": "idle"}))
                    print("💤 대기 모드로 전환")

        except websockets.exceptions.ConnectionClosed:
            print("❌ 프론트엔드 연결이 끊어졌습니다.")


async def main():
    # 0.0.0.0으로 열어야 도커 외부(프론트엔드)에서 접속 가능
    server = await websockets.serve(handle_client, "0.0.0.0", 8765)
    print("🚀 파이썬 하드웨어 에이전트 시작됨 (ws://0.0.0.0:8765)")
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())