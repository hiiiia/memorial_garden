# backend/app/utils/notifier.py (경로는 프로젝트 구조에 맞게 조정하세요)
import httpx
import os
import json

from core.config import settings
from db.models import Guardian

from api.v1.utils.security import decrypt_token # 복호화 함수


SLACK_CHANNEL= settings.SLACK_CHANNEL
SLACK_TOKEN = settings.SLACK_TOKEN


SLACK_TOKEN = settings.SLACK_TOKEN
SLACK_CHANNEL = settings.SLACK_CHANNEL

async def send_emergency_alert(
    dependent_name: str, 
    guardian_name: str, 
    guardian_phone: str, 
    risk_score: float, 
    summary: str, 
    text: str
):
    """위험 수치가 기준을 넘었을 때 보호자(관리자)에게 긴급 알림을 보냅니다."""
    
    print(f"🚨 *[긴급 알림] {guardian_name}님, {dependent_name} 어르신의 위험 징후가 감지되었습니다!* 🚨")
    # 1. 토큰이나 채널 설정이 안 되어 있으면 건너뛰기
    if not SLACK_TOKEN or not SLACK_CHANNEL:
        print("[Alert Warning] 슬랙 토큰 또는 채널이 설정되지 않아 알림을 건너뜁니다.")
        return

    # 2. 슬랙 Web API 엔드포인트 및 헤더 설정
    slack_api_url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {SLACK_TOKEN}" # 🌟 토큰을 헤더에 담아서 인증합니다
    }

    # 3. 슬랙에 보낼 메시지 폼 (channel 속성이 추가됨)
    slack_message = {
        "channel": SLACK_CHANNEL, # 메시지를 보낼 대상 채널 ID
        "text": f"🚨 *[긴급 알림] {guardian_name}님, {dependent_name} 어르신의 위험 징후가 감지되었습니다!* 🚨",
        "attachments": [
            {
                "color": "#FF0000",
                "fields": [
                    {"title": "위험도 점수 (Risk Score)", "value": f"*{int(risk_score * 100)} 점*", "short": True},
                    {"title": "보호자 연락처", "value": f"{guardian_phone}", "short": True},
                    {"title": "상태 요약", "value": summary, "short": False},
                    {"title": "대화 원본", "value": f"> {text}", "short": False}
                ]
            }
        ]
    }

    # 4. API 호출
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(slack_api_url, headers=headers, json=slack_message, timeout=10.0)
            
            # 슬랙 API는 실패해도 200을 주고 안의 json에 "ok": false를 뱉는 경우가 있어서 확인이 필요합니다.
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get("ok"):
                print(f"[Alert] 🚨 슬랙 긴급 알림 발송 성공! (Target: {dependent_name})")
            else:
                print(f"[Alert Error] 발송 실패: {response_data.get('error', response.text)}")
                
        except Exception as e:
            print(f"[Alert Exception] 슬랙 통신 에러: {e}")
            
            
            
            
async def send_kakao_alert(guardian: Guardian, dependent_name: str, risk_score: float, summary: str):
    """
    보호자의 카카오톡(나에게 보내기)으로 긴급 알림을 전송합니다.
    """
    # 1. 토큰 존재 여부 확인
    if not guardian.kakao_access_token:
        print(f"[Kakao Warning] {guardian.name} 보호자는 카카오톡 연동이 되어있지 않습니다.")
        return

    # 2. DB에 저장된 암호화된 토큰을 원본으로 복호화
    access_token = decrypt_token(guardian.kakao_access_token)

    # 3. 카카오 '나에게 보내기' API 주소 및 헤더 설정
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {
        "Authorization": f"Bearer {access_token}",
        # 카카오는 반드시 아래 Content-Type을 요구합니다.
        "Content-Type": "application/x-www-form-urlencoded" 
    }

    # 4. 카카오톡에 띄울 예쁜 메시지 템플릿 구성
    template_object = {
        "object_type": "text",
        "text": f"🚨 [긴급 알림] 🚨\n{guardian.name}님, {dependent_name} 어르신의 위험 징후가 감지되었습니다!\n\n■ 위험도: {int(risk_score * 100)}점\n■ AI 요약: {summary}",
        "link": {
            "web_url": f"{settings.FRONTEND_URL}", # 추후 프론트엔드 도메인으로 변경
            "mobile_web_url": f"{settings.FRONTEND_URL}"
        },
        "button_title": "상세 상태 확인하기"
    }

    # API 스펙에 맞게 json 텍스트로 변환하여 data 딕셔너리에 담기
    data = {
        "template_object": json.dumps(template_object)
    }

    # 5. 전송 실행
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, data=data, timeout=10.0)
            res_data = response.json()
            
            # 카카오 API는 성공하면 결과 코드로 0을 줍니다.
            if response.status_code == 200 and res_data.get("result_code") == 0:
                print(f"[Kakao Alert] 🚨 카카오톡 긴급 알림 쏘기 성공! (Target: {guardian.name})")
            else:
                print(f"[Kakao Alert Error] 발송 실패: {res_data}")
                
        except Exception as e:
            print(f"[Kakao Alert Exception] 서버 통신 에러: {e}")