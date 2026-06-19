from openai import OpenAI

# GX10 로컬 서버의 Ollama 주소
client = OpenAI(
    base_url="http://codu.ddns.net:11434/v1",
    api_key="ollama" # (Ollama는 사실 api key를 무시하지만 형식상 유지)
)

# 💡 추천 모델 적용 (Qwen 2.5 3B)
LLM_MODEL = "qwen2.5:3b"

def get_routing_from_gx10(raw_text):
    print(f"🚀 GX10 서버({LLM_MODEL})로 라우팅 요청 중...")
    
    # 앞서 구성한 퓨샷(Few-shot) 메시지 배열을 그대로 사용
    messages = [
        {"role": "system", "content": "당신은 독거노인을 위한 로봇의 라우터입니다. JSON만 출력하세요... (생략)"},
        {"role": "user", "content": "오늘 비가 오네."},
        {"role": "assistant", "content": '{"intent": "SIMPLE_CHAT", "privacy_flag": false, "local_action": null, "local_reply": "비가 오니 따뜻한 차 한 잔 어떠세요?"}'},
        {"role": "user", "content": raw_text}
    ]

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.0,
            # 🌟 매우 중요: Ollama에게 JSON 포맷 강제
            response_format={"type": "json_object"} 
        )
        
        # Ollama가 반환한 JSON 문자열 파싱
        result_json = response.choices[0].message.content
        return result_json

    except Exception as e:
        print(f"❌ GX10 서버 통신 에러: {e}")
        return None
    
# test.py 맨 아래 추가/수정
if __name__ == "__main__":
    test_text = "오늘 비가 오네, 무릎이 쑤신다."
    
    # 함수 실행 결과를 변수에 담고
    result = get_routing_from_gx10(test_text)
    
    # 화면에 출력!
    print("✨ [최종 결과]:", result)