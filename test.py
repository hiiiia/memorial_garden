from openai import OpenAI

client = OpenAI(
    base_url="http://codu.ddns.net:11434/v1",
    api_key="ollama"
)

response = client.chat.completions.create(
    model="gemma4:12b",
    messages=[
        {"role":"user","content":"안녕"}
    ]
)

print(response.choices[0].message.content)



# import os
# import certifi
# import asyncio
# import ssl
# from datetime import datetime

# if hasattr(ssl.SSLContext, '_load_windows_store_certs'):
#     ssl.SSLContext._load_windows_store_certs = lambda self, storename, purpose: None

# import edge_tts

# async def generate_tts_audio_edge(text: str, job_id: str) -> str:
#     """Edge-TTS를 사용하여 무료로 고음질 음성을 생성합니다."""
#     # 1. 오늘 날짜로 폴더 경로 만들기 (예: shared_uploads/20260611)
#     today_str = datetime.now().strftime("%Y%m%d")
#     base_dir = os.path.join("shared_uploads", today_str)
    
#     # 폴더가 없으면 자동으로 생성
#     os.makedirs(base_dir, exist_ok=True)
    
#     # 2. 최종 저장 경로와 URL 세팅
#     file_name = f"reply_{job_id}.mp3"
#     save_path = os.path.join(base_dir, file_name)
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

# if __name__ == "__main__":
#     test_text = "오늘 날씨가 너무 좋아서 동네 뒷산에 산책을 다녀왔어. 옛날에 우리 영수 어릴 때 같이 손잡고 올라가던 기억이 나서 기분이 참 좋더라구."
    
#     # async 함수를 동기 환경에서 실행하는 방법
#     asyncio.run(generate_tts_audio_edge(job_id="asdfasf", text=test_text))