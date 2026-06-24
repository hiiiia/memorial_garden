# backend\app\api\v1\callbacks\jobs.py
from fastapi import APIRouter, Header, HTTPException, Depends, Request, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
import os
import httpx
import aiofiles
import asyncio
from datetime import datetime
from typing import Optional
import uuid 

# openAPI TTS 사용시 edge-tts는 주석처리
# import edge_tts

from db.database import get_db 
from db import models
from core.config import settings
from api.v1.utils.notifier import send_emergency_alert, send_kakao_alert
from api.v1.utils.security import verify_ai_token
from core.response import unified_response
from api.v1.ws.ws_router import notify_new_diary_to_device

router = APIRouter()

class HealthcareAnalysisData(BaseModel):
    risk_score: float
    primary_emotion: str
    llm_summary: str
    image_url: Optional[str] = None
    diary_text: Optional[str] = None
    depression_score: float
    cognitive_decline_score: float
    care_level: str
    # 음향 바이오마커 추가
    speech_rate: float
    pause_ratio: float
    pitch_variance: float

class LogCreateRequest(BaseModel):
    user_id: str
    status: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    analysis_data: HealthcareAnalysisData

@router.post("/analyze-result", summary="AI 서버 심층 분석 결과 다이렉트 적재")
async def receive_healthcare_log(
    request: LogCreateRequest, 
    req: Request, # 서버의 기본 도메인을 동적으로 가져오기 위해 추가
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    AI 서버가 비동기로 분석을 완료한 헬스케어 데이터를 DB에 저장.
    이미지 URL이 포함되어 있다면 백엔드 서버로 다운로드 후 로컬 URL로 변환하여 적재.
    """
    try:
        if request.status == "FAILED":
            print(f"[Backend] AI 서버 분석 실패 로그 수신: {request.error_message}")
            return {"message": "Failure log received safely."}

        analysis = request.analysis_data
        
        # 1. 이미지 다운로드 및 로컬 URL 변환 로직
        final_image_url = analysis.image_url

        if final_image_url and final_image_url.startswith("http"):
            save_dir = "/app/uploads/diary_images" # 서버 환경에 맞춰 경로 수정
            os.makedirs(save_dir, exist_ok=True)
            
            # 충돌 방지를 위해 UUID로 고유 파일명 생성
            unique_filename = f"diary_{uuid.uuid4().hex}.png"
            save_path = os.path.join(save_dir, unique_filename)
            
            try:
                print(f"[Backend] AI 서버로부터 이미지를 다운로드합니다: {final_image_url}")
                # 비동기로 이미지 다운로드
                async with httpx.AsyncClient(timeout=30.0) as client:
                    img_response = await client.get(final_image_url)
                    img_response.raise_for_status()
                    
                    with open(save_path, "wb") as f:
                        f.write(img_response.content)
                
                # Request 객체를 사용해 현재 백엔드 도메인을 동적으로 획득 (예: http://localhost:8000)
                base_url = str(req.base_url).rstrip("/")
                final_image_url = f"{base_url}/static/diary_images/{unique_filename}"
                print(f"[Backend] 로컬 저장 완료. DB 적재 URL: {final_image_url}")
                
            except Exception as img_err:
                print(f"[Backend Error] 이미지 다운로드 실패 (원본 URL 유지): {img_err}")
                # 실패하면 원본 URL을 그대로 유지하도록 처리
                
        # 2. Log 테이블에 새 레코드 생성
        new_log = models.Log(
            dependent_id=request.user_id,
            status=request.status,
            risk_score=analysis.risk_score,
            depression_score=analysis.depression_score,
            cognitive_decline_score=analysis.cognitive_decline_score,
            primary_emotion=analysis.primary_emotion,
            llm_summary=analysis.llm_summary,
            image_url=final_image_url, 
            diary_text=analysis.diary_text,
            speech_rate=analysis.speech_rate,
            pause_ratio=analysis.pause_ratio,
            pitch_variance=analysis.pitch_variance
        )
        
        try:
            db.add(new_log)
            db.flush()

            print(f"[Backend] 새로운 헬스케어 로그 (Log ID: {new_log.id})")
            
            # ====================================================
            # 🚨 위험도 평가, Alert DB 기록 및 보호자 알림 발송
            # ====================================================
            DANGER_THRESHOLD = 70.0
            
            # 1) Alert 테이블에 상태 기록 (위험하면 PENDING, 정상이면 RESOLVED)
            trigger_type = "AI_RISK" if analysis.risk_score >= DANGER_THRESHOLD else "INFO"
            
            new_alert = models.Alert(
                dependent_id=request.user_id,
                log_id=new_log.id,
                trigger_type=trigger_type,
                status="RESOLVED" if trigger_type == "INFO" else "PENDING"
            )
            
            db.commit() 
            db.refresh(new_log)
            
            print(f"[Backend] 새로운 헬스케어 로그 및 Alert 적재 완료 (Log ID: {new_log.id})")
            
            # 2) 위험 기준치 초과 시 외부 알림 발송
            if analysis.risk_score >= DANGER_THRESHOLD:
                # 연결된 보호자 조회
                connected_mappings = db.query(models.GuardianDependentMapping).filter(
                    models.GuardianDependentMapping.dependent_id == request.user_id,
                    models.GuardianDependentMapping.status == "CONNECTED"
                ).all()
                
                for mapping in connected_mappings:
                    guardian_obj = mapping.guardian
                    # 어르신 이름 가져오기 (관계 매핑에 dependent가 연결되어 있다고 가정)
                    target_name = mapping.dependent.name if hasattr(mapping, 'dependent') and mapping.dependent else "어르신"
                    
                    print(f"[Alert] 위험 감지! {guardian_obj.name} 보호자에게 알림 발송 예약.")
                    
                    # 🌟 응답 지연이 없도록 FastAPI background_tasks로 외부 통신 넘기기
                    background_tasks.add_task(
                        send_emergency_alert,
                        risk_score=analysis.risk_score,
                        summary=analysis.llm_summary,
                        text=analysis.diary_text, # 레거시의 stt_text 대신 현재 사용중인 diary_text로 교체
                        dependent_name=target_name,
                        guardian_phone=guardian_obj.phone,
                        guardian_name=guardian_obj.name
                    )
                    background_tasks.add_task(
                        send_kakao_alert,
                        guardian=guardian_obj,
                        dependent_name=target_name,
                        risk_score=analysis.risk_score,
                        summary=analysis.llm_summary
                    )
            # ====================================================

            # 기존: 어르신 기기(프론트엔드)로 새 일기 도착 웹소켓 알림
            background_tasks.add_task(
                notify_new_diary_to_device,
                request.user_id,
                new_log
            )
            
            return {"message": "Log successfully saved.", "log_id": new_log.id}
            
        except Exception as e:
            db.rollback()
            print(f"[Backend Error] 로그 저장 중 DB 오류 발생: {e}")
            raise HTTPException(status_code=500, detail="Database insertion failed.")

    except Exception as e:
        db.rollback()
        print(f"[Backend Error] 로그 저장 중 DB 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="Database insertion failed.")



    
    
    
# # --- 1. Pydantic 스키마 정의 ---
# class AnalysisData(BaseModel):
#     risk_score: float
#     primary_emotion: str
#     llm_summary: str
#     reply_text: str
#     stt_text : str
#     image_url: str = None # AI가 생성한 그림일기 URL 추가
#     vector_embedding: list[float]  = None

# class CallbackRequest(BaseModel):
#     user_id: str
#     status: str
#     analysis_data: AnalysisData

# # AI 빠른 응답 결과 스키마
# class FastChatCallbackPayload(BaseModel):
#     job_id: str
#     status: str
#     reply_text: str
    
# # --- 2. 보안 토큰 검증 함수 ---
# AI_SECRET_TOKEN = settings.AI_SECRET_TOKEN
# OPENAI_API_KEY = settings.OPENAI_API_KEY


# # async def generate_tts_audio_open_ai(text: str, job_id: str) -> str:
# #     """OpenAI TTS를 호출하여 음성 파일을 생성하고 경로를 반환합니다."""
    
# #     # 저장할 파일명과 경로 세팅 (기존에 세팅하신 shared_uploads 폴더 활용)
# #     file_name = f"reply_{job_id}.mp3"
# #     save_path = os.path.join("shared_uploads", file_name)
# #     static_url = f"http://localhost:8000/static/{file_name}" # 스피커가 접근할 URL
    
# #     url = "https://api.openai.com/v1/audio/speech"
# #     headers = {
# #         "Authorization": f"Bearer {OPENAI_API_KEY}",
# #         "Content-Type": "application/json"
# #     }
# #     data = {
# #         "model": "tts-1",
# #         "input": text,
# #         "voice": "nova", # nova: 다정하고 상냥한 여성 톤 / alloy: 중성적 톤 / onyx: 남성 톤
# #         "response_format": "mp3" 
# #     }
    
# #     print(f"[TTS] 🎙️ 음성 생성 요청 중... (Text: {text[:15]}...)")
    
# #     async with httpx.AsyncClient() as client:
# #         response = await client.post(url, headers=headers, json=data, timeout=30.0)
        
# #         if response.status_code == 200:
# #             # 스트리밍으로 받아서 파일로 저장 (aiofiles 사용)
# #             async with aiofiles.open(save_path, 'wb') as f:
# #                 await f.write(response.content)
# #             print(f"[TTS] ✅ 음성 파일 생성 완료: {save_path}")
# #             return static_url
# #         else:
# #             print(f"[TTS Error] 음성 생성 실패: {response.text}")
# #             return None

# async def generate_tts_audio_edge(text: str, job_id: str) -> str:
#     """Edge-TTS를 사용하여 무료로 고음질 음성을 생성합니다."""
#     # 1. 오늘 날짜로 폴더 경로 만들기 (예: shared_uploads/20260529)
#     today_str = datetime.now().strftime("%Y%m%d")
#     base_dir = os.path.join("shared_uploads", today_str)
    
#     # 폴더가 없으면 자동으로 생성
#     os.makedirs(base_dir, exist_ok=True)
    
#     # 2. 최종 저장 경로와 URL 세팅
#     file_name = f"reply_{job_id}.mp3"
#     save_path = os.path.join(base_dir, file_name) # shared_uploads/20260529/reply_...mp3
#     static_url = f"http://localhost:8000/static/{today_str}/{file_name}"
    
#     voice = "ko-KR-SunHiNeural"
    
#     print(f"[TTS] 🎙️ 무료 음성 생성 요청 중... (Text: {text[:15]}...)")
    
#     try:
#         communicate = edge_tts.Communicate(text, voice)
#         await communicate.save(save_path)
        
#         print(f"[TTS] ✅ 무료 음성 파일 생성 완료: {save_path}")
#         return static_url
#     except Exception as e:
#         print(f"[TTS Error] 음성 생성 실패: {e}")
#         return None


# # --- 3. 콜백 API 엔드포인트 ---
# @router.post("/{job_id}/analyzing-result")
# async def receive_ai_callback(
#     job_id: str, 
#     payload: CallbackRequest, 
#     token: str = Depends(verify_ai_token),
#     db: Session = Depends(get_db)
# ):
#     print(f"\n[Backend] 🔔 AI 서버로부터 콜백 수신 완료! (Job ID: {job_id})")
    
#     # 1. DB에서 해당 job_id 찾기
#     log_record = db.query(models.Log).filter(models.Log.id == job_id).first()
    
#     if not log_record:
#         print(f"[Backend Error] DB에서 해당 Job ID({job_id})를 찾을 수 없습니다.")
#         raise HTTPException(status_code=404, detail="Job ID not found")
    
#     if payload.status == "COMPLETED":
#         # 2. DB 업데이트 (분석 데이터 매핑 및 그림일기 URL 추가)
#         log_record.status = "COMPLETED"
#         log_record.risk_score = payload.analysis_data.risk_score
#         log_record.primary_emotion = payload.analysis_data.primary_emotion
#         log_record.llm_summary = payload.analysis_data.llm_summary
#         log_record.reply_text = payload.analysis_data.reply_text
#         log_record.stt_text = payload.analysis_data.stt_text
        
#         # 그림일기 이미지가 생성되어 넘어왔다면 저장
#         if payload.analysis_data.image_url:
#             log_record.image_url = payload.analysis_data.image_url
        
#         # RAG 벡터 저장
#         if payload.analysis_data.vector_embedding:
#             log_record.vector_embedding = payload.analysis_data.vector_embedding
            
#         # TTS 생성 및 파일 경로 저장
#         if payload.analysis_data.reply_text:
#             audio_url = await generate_tts_audio_edge(payload.analysis_data.reply_text, job_id)
#             if audio_url:
#                 log_record.reply_audio_url = audio_url 
                
#     elif payload.status == "FAILED":
#         print("[Backend] 🚨 AI 분석 실패 보고를 받았습니다.")
#         log_record.status = "FAILED"
        
#     # 3. 트랜잭션 확정 (DB에 영구 저장)
#     try:
#         db.commit()
#     except Exception as e:
#         db.rollback()
#         print(f"[Backend Error] DB 커밋 중 에러 발생: {e}")
#         raise HTTPException(status_code=500, detail="Database commit failed")
    
#     # 4. 위험도 평가 및 알림 발송 로직
#     DANGER_THRESHOLD = 70.0 # 프론트엔드 위험 기준(70점)에 맞춤
        
#     if payload.status == "COMPLETED":
#         dependent = log_record.dependent
#         target_name = dependent.name if dependent else "어르신"
        
#         #  매핑 테이블을 통해 현재 'CONNECTED' 상태인 모든 보호자 찾기
#         connected_mappings = db.query(models.GuardianDependentMapping).filter(
#             models.GuardianDependentMapping.dependent_id == log_record.dependent_id,
#             models.GuardianDependentMapping.status == "CONNECTED"
#         ).all()

#         # 대시보드 위젯에 띄워줄 알림을 DB(Alert 테이블)에 저장
#         trigger_type = "AI_RISK" if payload.analysis_data.risk_score >= DANGER_THRESHOLD else "INFO"
        
#         new_alert = models.Alert(
#             dependent_id=log_record.dependent_id,
#             log_id=log_record.id,
#             trigger_type=trigger_type,
#             status="RESOLVED" if trigger_type == "INFO" else "PENDING"
#         )
#         db.add(new_alert)
#         db.commit()
        
#         # 위험 수치를 넘었을 때만 외부 메신저(카톡/슬랙) 알림 발송
#         if payload.analysis_data.risk_score >= DANGER_THRESHOLD:
#             for mapping in connected_mappings:
#                 guardian_obj = mapping.guardian
#                 print(f"[Alert] 위험 감지! {guardian_obj.name} 보호자에게 알림을 발송합니다.")
                
#                 await asyncio.gather(
#                     send_emergency_alert(
#                         risk_score=payload.analysis_data.risk_score,
#                         summary=payload.analysis_data.llm_summary,
#                         text=payload.analysis_data.stt_text,
#                         dependent_name=target_name,
#                         guardian_phone=guardian_obj.phone,
#                         guardian_name=guardian_obj.name
#                     ),
#                     send_kakao_alert(
#                         guardian=guardian_obj,
#                         dependent_name=target_name,
#                         risk_score=payload.analysis_data.risk_score,
#                         summary=payload.analysis_data.llm_summary
#                     )
#                 )

#     return unified_response(
#         status_code= 200,
#         message="데이터 저장 완료",
#         data={
#             "job_id" : job_id
#         }
#     )
    
# # 빠른 응답용(Rag)
# @router.post("/{job_id}/fast-chat")
# async def receive_fast_chat_callback(job_id: str, payload: FastChatCallbackPayload, db: Session = Depends(get_db)):
#     #  FastChat 테이블 조회
#     chat_record = db.query(models.FastChat).filter(models.FastChat.id == job_id).first()
    
#     if not chat_record:
#         return {"status": "error", "message": "Job ID not found"}

#     if payload.status == "COMPLETED":
#         audio_url = await generate_tts_audio_edge(payload.reply_text, job_id)
        
#         chat_record.reply_text = payload.reply_text
#         if audio_url:
#             chat_record.reply_audio_url = audio_url
#         chat_record.status = "COMPLETED"
#     else:
#         chat_record.status = "FAILED"
        
#     db.commit()
#     return {"status": "success"}