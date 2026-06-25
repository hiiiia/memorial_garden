from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketException, status
import json
from db.database import SessionLocal 
from db.models import GuardianDependentMapping, Log, DeviceSetting
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
    # 기기가 연결되었을 때 초기화 작업 (밀린 요청 검사 및 초기 설정값 전송)
    # ==============================================================
    db = SessionLocal()
    try:
        # --- [추가됨] 1. 기기 설정 조회 및 전송 ---
        setting = db.query(DeviceSetting).filter(DeviceSetting.dependent_id == dependent_id).first()
        if not setting:
            # 설정이 없다면 기본값으로 생성
            setting = DeviceSetting(dependent_id=dependent_id)
            db.add(setting)
            db.commit()
            db.refresh(setting)

        settings_payload = {
            "action": "INIT_SETTINGS",
            "data": {
                "proactive_greeting_enabled": setting.proactive_greeting_enabled
            }
        }
        await websocket.send_text(json.dumps(settings_payload))
        print(f"⚙️ [WS] 초기 기기 설정값 전송 완료: {dependent_id}")
        
        # --- [기존] 2. 밀린 연동 요청(PENDING) 팝업 전송 ---
        pending_requests = db.query(GuardianDependentMapping).filter(
            GuardianDependentMapping.dependent_id == dependent_id,
            GuardianDependentMapping.status == "PENDING"
        ).all()
        
        for req in pending_requests:
            guardian_name = req.guardian.name if req.guardian else "가족" 
            
            payload = {
                "action": "SHOW_PAIRING_POPUP",
                "data": {
                    "mapping_id": req.id,
                    "guardian_name": guardian_name,
                    "message": f"{guardian_name} 님이 보호자 연동을 요청했습니다. 수락하시겠습니까?"
                }
            }
            await websocket.send_text(json.dumps(payload))
            print(f"📦 [WS] 오프라인 때 밀렸던 팝업 전송 완료: {dependent_id}")
            
    except Exception as e:
        print(f"🚨 기기 초기화(설정/밀린 요청 검사) 중 오류: {e}")
        db.rollback() # 에러 발생 시 롤백 추가
    finally:
        db.close()
    # ==============================================================
    # 실시간 통신 루프 (메시지 수신)
    # ==============================================================
    try:
        while True:
            data = await websocket.receive_text()
            
            # JSON 파싱 에러 방어 로직
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                print(f"⚠️ [WS] 잘못된 데이터 형식 수신: {data}")
                continue
                
            action = payload.get("action")
            print(f"📥 [클라우드 WS 수신] dependent_id={dependent_id}, data={payload}")
            
            # 5. 어르신이 연동을 수락/거절했을 때의 처리 로직
            if action in ["PAIRING_ACCEPTED", "PAIRING_REJECTED"]:
                mapping_id = payload.get("data", {}).get("mapping_id") or payload.get("mapping_id")
                
                update_db = SessionLocal()
                try:
                    mapping = update_db.query(GuardianDependentMapping).filter(
                        GuardianDependentMapping.id == mapping_id
                    ).first()
                    
                    if mapping:
                        if action == "PAIRING_ACCEPTED":
                            # 수락 시 CONNECTED 상태로 변경
                            mapping.status = "CONNECTED"
                            update_db.commit()
                            print(f"🤝 [WS] 연동 수락: 상태를 CONNECTED로 변경 완료 (ID: {mapping_id})")
                            
                        elif action == "PAIRING_REJECTED":
                            # 거절 시 mapping 테이블에서 레코드 삭제
                            update_db.delete(mapping)
                            update_db.commit()
                            print(f"🗑️ [WS] 연동 거절: mapping 테이블에서 데이터 삭제 완료 (ID: {mapping_id})")
                    else:
                        print(f"⚠️ [WS] 처리 실패: 존재하지 않는 연동 ID ({mapping_id})")
                        
                except Exception as e:
                    update_db.rollback()  # 오류 발생 시 롤백 안전장치 추가
                    print(f"🚨 연동 처리 중 DB 오류 (Action: {action}): {e}")
                finally:
                    update_db.close()
            
                
    except WebSocketDisconnect:
        # 연결이 끊어졌을 때 매니저에서 제거
        device_ws_manager.disconnect(dependent_id)


# AI 오케스트레이터가 작업 완료 후 호출하는 콜백 라우터 또는 내부 서비스 함수
async def notify_new_diary_to_device(dependent_id: str, new_diary: Log):
    """
    그림일기가 생성된 직후, 연결된 어르신 기기로 웹소켓 알림을 발송합니다.
    """
    # 1. 기기가 현재 웹소켓에 연결되어 있는지 확인
    if dependent_id in device_ws_manager.active_connections:
        print(f"📡 [WS] {dependent_id} 기기가 온라인입니다. 새 일기 알림을 전송합니다.")
        
        # 2. 어르신 화면(React)이 알아들을 수 있는 포맷으로 페이로드 작성
        payload = {
            "action": "NEW_DIARY_ARRIVED",
            "data": {
                "diary_id": new_diary.id,
                "title": "새로운 추억이 도착했어요",
                "message": "어르신, 방금 나누신 대화로 예쁜 그림일기가 도착했어요! 함께 보실래요?",
                "image_url": new_diary.image_url # 팝업에 미리보기 썸네일을 띄워줄 수도 있습니다.
            }
        }
        
        # 3. 실시간 전송!
        try:
            await device_ws_manager.send_personal_message(payload, dependent_id)
            print(f"✅ [WS] 새 일기 알림 전송 성공: {new_diary.id}")
        except Exception as e:
            print(f"🚨 [WS] 알림 전송 중 에러 발생: {e}")
            
    else:
        # 기기가 꺼져있다면 나중에 켰을 때 GET API로 불러오게 되므로 로그만 남깁니다.
        print(f"💤 [WS] {dependent_id} 기기가 오프라인 상태입니다. (알림 생략)")