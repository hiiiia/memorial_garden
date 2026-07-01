# backend/app/utils/notifier.py (경로는 프로젝트 구조에 맞게 조정하세요)
import httpx
import os
import json

from core.config import settings
from db.models import Guardian
from db.database import get_db

from api.v1.utils.security import decrypt_token # 복호화 함수
from api.v1.auth.auth import refresh_kakao_token_procedure

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
            
async def send_slack_diary_alert(
    guardian_name: str, 
    dependent_name: str, 
    diary_text: str, 
    summary: str, 
    emotion: str, 
    image_url: str
):
    """새로운 그림일기가 생성되었을 때 슬랙(보호자/관리자 채널)으로 알림과 이미지를 보냅니다."""
    
    print(f"🌷 [Slack Diary Alert] {guardian_name}님께 {dependent_name} 어르신의 일기 알림 전송 준비 중...")
    
    # 1. 토큰이나 채널 설정이 안 되어 있으면 건너뛰기 (전역 변수 또는 settings에서 가져온다고 가정)
    if not SLACK_TOKEN or not SLACK_CHANNEL:
        print("[Slack Warning] 슬랙 토큰 또는 채널이 설정되지 않아 알림을 건너뜁니다.")
        return

    # 2. 슬랙 Web API 엔드포인트 및 헤더 설정
    slack_api_url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {SLACK_TOKEN}"
    }

    # 3. 슬랙에 보낼 메시지 폼 (Attachments를 사용하여 이미지와 함께 예쁘게 렌더링)
    slack_message = {
        "channel": SLACK_CHANNEL,
        "text": f"🌷 *[{guardian_name} 보호자님] {dependent_name} 어르신의 새로운 기억이 정원에 피어났습니다!*",
        "attachments": [
            {
                "color": "#4CAF50",  # 기억정원 테마에 맞는 따뜻한 초록색
                "pretext": "오늘의 일기와 AI 상태 요약이 도착했습니다.",
                "fields": [
                    {"title": "📝 오늘의 이야기", "value": f"> {diary_text}", "short": False},
                    {"title": "💡 상태 요약", "value": summary, "short": False},
                    {"title": "🎭 주요 감정", "value": emotion, "short": True}
                ],
                "image_url": image_url,  # 슬랙에서 이미지를 미리보기(썸네일)로 띄워줍니다.
                "fallback": "새로운 그림일기가 도착했습니다."
            }
        ]
    }

    # 4. API 호출
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(slack_api_url, headers=headers, json=slack_message, timeout=10.0)
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get("ok"):
                print(f"[Slack Alert] 🌷 슬랙 일기 알림 발송 성공! (Target: {dependent_name})")
            else:
                print(f"[Slack Alert Error] 일기 발송 실패: {response_data.get('error', response.text)}")
                
        except Exception as e:
            print(f"[Slack Alert Exception] 슬랙 통신 에러: {e}")            
 
            
async def send_kakao_alert(guardian, dependent_name: str, risk_score: float, summary: str, db: get_db):
    """
    보호자의 카카오톡(나에게 보내기)으로 긴급 알림을 전송합니다.
    토큰 만료(-401) 에러가 발생하면 자동으로 리프레시 토큰을 이용해 갱신 후 1회 재시도합니다.
    """
    # 1. 토큰 존재 여부 확인
    if not guardian.kakao_access_token:
        print(f"[Kakao Warning] {guardian.name} 보호자는 카카오톡 연동이 되어있지 않습니다.")
        return

    # 2. DB에 저장된 암호화된 토큰을 원본으로 복호화
    try:
        access_token = decrypt_token(guardian.kakao_access_token)
    except Exception as e:
        print(f"[Kakao Alert Error] 토큰 복호화 실패: {e}")
        return

    # 3. 카카오 '나에게 보내기' API 주소 및 헤더 설정
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {
        "Authorization": f"Bearer {access_token}",
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
    # ensure_ascii=False 를 넣으면 한글이 유니코드(\uXXXX)로 깨지지 않고 예쁘게 전송됩니다.
    data = {
        "template_object": json.dumps(template_object, ensure_ascii=False)
    }

    # 5. 전송 실행 및 Retry 파이프라인
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, data=data, timeout=10.0)
            res_data = response.json()
            
            # 토큰 만료(-401) 감지 시 자동 갱신 및 재시도
            if response.status_code == 401 or res_data.get("code") == -401:
                print(f"🔄 [Kakao Alert] 토큰 만료 감지(-401). {guardian.name}님의 토큰 갱신을 시도합니다.")
                
                # 이전에 만든 리프레시 함수 호출 (내부에서 DB 암호화/저장까지 처리됨)
                new_access_token = await refresh_kakao_token_procedure(guardian.id, db)
                
                if new_access_token:
                    # 새 토큰으로 헤더 교체
                    headers["Authorization"] = f"Bearer {new_access_token}"
                    print(f"🚀 [Kakao Alert] 새 토큰 발급 성공! 재발송을 시도합니다.")
                    
                    # 동일한 데이터로 다시 전송
                    retry_response = await client.post(url, headers=headers, data=data, timeout=10.0)
                    retry_res_data = retry_response.json()
                    
                    if retry_response.status_code == 200 and retry_res_data.get("result_code") == 0:
                        print(f"[Kakao Alert] 🚨 (Retry) 카카오톡 알림 쏘기 성공! (Target: {guardian.name})")
                    else:
                        print(f"[Kakao Alert Error] 재시도 발송 실패: {retry_res_data}")
                else:
                    print(f"❌ [Kakao Alert] 리프레시 토큰이 만료되었습니다. {guardian.name}님의 재연동이 필요합니다.")
                    
            # 정상 발송 성공 시
            elif response.status_code == 200 and res_data.get("result_code") == 0:
                print(f"[Kakao Alert] 🚨 카카오톡 긴급 알림 쏘기 성공! (Target: {guardian.name})")
                
            # 토큰 만료가 아닌 다른 카카오 API 에러 시
            else:
                print(f"[Kakao Alert Error] 발송 실패: {res_data}")
                
        except Exception as e:
            print(f"[Kakao Alert Exception] 서버 통신 에러: {e}")
            

async def send_kakao_diary_alert(guardian, dependent_name: str, diary_text: str, summary: str, emotion: str, image_url: str, db):
    """
    새로운 그림일기가 생성되었을 때 보호자의 카카오톡(나에게 보내기)으로 알림을 전송합니다.
    토큰 만료(-401) 에러가 발생하면 자동으로 리프레시 토큰을 이용해 갱신 후 1회 재시도합니다.
    """
    # 1. 토큰 존재 여부 확인
    if not guardian.kakao_access_token:
        print(f"[Kakao Warning] {guardian.name} 보호자는 카카오톡 연동이 되어있지 않습니다.")
        return

    # 2. DB에 저장된 암호화된 토큰을 원본으로 복호화
    try:
        access_token = decrypt_token(guardian.kakao_access_token)
    except Exception as e:
        print(f"[Kakao Diary Error] 토큰 복호화 실패: {e}")
        return

    # 3. 카카오 '나에게 보내기' API 주소 및 헤더 설정
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded" 
    }

    # 4. 카카오톡 feed 템플릿 구성 (이미지를 예쁘게 띄우기 위함)
    # 카카오톡 설명(description)란은 글자 수 제한이 있으므로 일기 내용은 적절히 자르는 것이 좋습니다.
    short_diary = diary_text if len(diary_text) <= 40 else diary_text[:40] + "..."
    
    template_object = {
        "object_type": "feed",
        "content": {
            "title": f"🌱 {dependent_name} 어르신의 새로운 기억이 피어났습니다.",
            "description": f"📝 이야기: \"{short_diary}\"\n💡 요약: {summary}\n(주요 감정: {emotion})",
            "image_url": image_url,  # 생성된 그림일기 이미지 URL
            "image_width": 800,
            "image_height": 800,
            "link": {
                "web_url": f"{settings.FRONTEND_URL}",
                "mobile_web_url": f"{settings.FRONTEND_URL}"
            }
        },
        "buttons": [
            {
                "title": "일기장 전체 보기",
                "link": {
                    "web_url": f"{settings.FRONTEND_URL}",
                    "mobile_web_url": f"{settings.FRONTEND_URL}"
                }
            }
        ]
    }

    # API 스펙에 맞게 json 텍스트로 변환
    data = {
        "template_object": json.dumps(template_object, ensure_ascii=False)
    }

    # 5. 전송 실행 및 Retry 파이프라인 (기존 로직과 동일)
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, data=data, timeout=10.0)
            res_data = response.json()
            
            # 토큰 만료(-401) 감지 시 자동 갱신 및 재시도
            if response.status_code == 401 or res_data.get("code") == -401:
                print(f"🔄 [Kakao Diary] 토큰 만료 감지(-401). {guardian.name}님의 토큰 갱신을 시도합니다.")
                
                new_access_token = await refresh_kakao_token_procedure(guardian.id, db)
                
                if new_access_token:
                    headers["Authorization"] = f"Bearer {new_access_token}"
                    print(f"🚀 [Kakao Diary] 새 토큰 발급 성공! 재발송을 시도합니다.")
                    
                    retry_response = await client.post(url, headers=headers, data=data, timeout=10.0)
                    retry_res_data = retry_response.json()
                    
                    if retry_response.status_code == 200 and retry_res_data.get("result_code") == 0:
                        print(f"[Kakao Diary] 🌷 (Retry) 카카오톡 일기 알림 성공! (Target: {guardian.name})")
                    else:
                        print(f"[Kakao Diary Error] 재시도 발송 실패: {retry_res_data}")
                else:
                    print(f"❌ [Kakao Diary] 리프레시 토큰이 만료되었습니다. {guardian.name}님의 재연동이 필요합니다.")
                    
            # 정상 발송 성공 시
            elif response.status_code == 200 and res_data.get("result_code") == 0:
                print(f"[Kakao Diary] 🌷 카카오톡 일기 알림 발송 성공! (Target: {guardian.name})")
                
            # 토큰 만료가 아닌 다른 카카오 API 에러 시
            else:
                print(f"[Kakao Diary Error] 발송 실패: {res_data}")
                
        except Exception as e:
            print(f"[Kakao Diary Exception] 서버 통신 에러: {e}")