from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketException, status
import json
from db.database import SessionLocal 
from db.models import GuardianDependentMapping
from api.v1.ws.websocket_manager import device_ws_manager
from api.v1.deps import verify_hw_jwt_token
ws_router = APIRouter()

@ws_router.websocket("/device/{dependent_id}")
async def websocket_endpoint(websocket: WebSocket, dependent_id: str):
    
    
    # 1. 헤더에서 토큰 추출
    auth_header = websocket.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    token = auth_header.split(" ")[1]

    # 2. [분리된 로직 호출] JWT 검증
    try:
        validated_id = verify_hw_jwt_token(token)
    except ValueError as e:
        print(f"🚫 [WS] 인증 실패: {e}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # 3. URL의 ID와 토큰의 ID가 일치하는지 보안 체크
    if validated_id != dependent_id:
        print(f"🚫 [WS] ID 불일치: 토큰({validated_id}) vs URL({dependent_id})")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    
    # 기기 연결 수락 및 매니저 등록
    await device_ws_manager.connect(dependent_id, websocket)
    
    # ==============================================================
    # 기기가 막 연결되었을 때, 혹시 밀린 연동 요청(PENDING)이 있는지 검사
    # ==============================================================
    db = SessionLocal()
    try:
        # 이 어르신에게 온 PENDING 상태의 연동 요청 조회
        pending_requests = db.query(GuardianDependentMapping).filter(
            GuardianDependentMapping.dependent_id == dependent_id,
            GuardianDependentMapping.status == "PENDING"
        ).all()
        
        for req in pending_requests:
            # 밀린 요청이 있다면, 연결되자마자 바로 팝업 명령 발송!
            # (주의: req.guardian.name 은 DB 관계 설정에 따라 다를 수 있습니다)
            guardian_name = req.guardian.name if req.guardian else "가족" 
            
            payload = {
                "action": "SHOW_PAIRING_POPUP",
                "data": {
                    "mapping_id": req.id,
                    "guardian_name": guardian_name,
                    "message": f"{guardian_name} 님이 기기 연동을 요청했습니다. 수락하시겠습니까?"
                }
            }
            await websocket.send_text(json.dumps(payload))
            print(f"📦 [WS] 오프라인 때 밀렸던 팝업 전송 완료: {dependent_id}")
            
    except Exception as e:
        print(f"🚨 밀린 요청 검사 중 오류: {e}")
    finally:
        db.close()
    # ==============================================================

    try:
        while True:
            # 2. 기기(React ➔ HW ➔ 백엔드)로부터 메시지 수신
            data = await websocket.receive_text()
            payload = json.loads(data)
            action = payload.get("action")
            
            print(f"📥 [클라우드 WS 수신] dependent_id={dependent_id}, data={payload}")

            # 3. [기존 로직 유지] 어르신이 기기에서 연동을 수락하거나 거절했을 때의 처리
            if action in ["PAIRING_ACCEPTED", "PAIRING_REJECTED"]:
                mapping_id = payload.get("mapping_id")
                # ... (DB 상태 변경 기존 코드) ...
                
    except WebSocketDisconnect:
        # 연결이 끊어졌을 때 매니저에서 제거
        device_ws_manager.disconnect(dependent_id)