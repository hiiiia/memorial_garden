from typing import Dict
from fastapi import WebSocket
import json

class DeviceWebSocketManager:
    def __init__(self):
        # key: dependent_id (또는 device_id), value: WebSocket 객체
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, dependent_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[dependent_id] = websocket
        print(f"🔌 [WS] 어르신 기기 연결 성공: dependent_id={dependent_id}")

    def disconnect(self, dependent_id: str):
        if dependent_id in self.active_connections:
            del self.active_connections[dependent_id]
            print(f"❌ [WS] 어르신 기기 연결 해제: dependent_id={dependent_id}")

    async def send_personal_message(self, message: dict, dependent_id: str) -> bool:
        """
        특정 어르신 기기에 실시간 JSON 메시지 발송
        발송 성공 시 True, 기기가 오프라인이거나 실패 시 False 반환
        """
        websocket = self.active_connections.get(dependent_id)
        if websocket:
            try:
                await websocket.send_text(json.dumps(message))
                print(f"📨 [WS] 실시간 메시지 전송 완료 to {dependent_id}: {message}")
                return True
            except Exception as e:
                print(f"⚠️ [WS] 메시지 전송 오류: {e}")
                self.disconnect(dependent_id)
                return False
        print(f"💤 [WS] 전송 실패: {dependent_id} 기기가 현재 오프라인 상태입니다.")
        return False

# 전역 싱글톤 객체로 생성하여 라우터들에서 공유
device_ws_manager = DeviceWebSocketManager()