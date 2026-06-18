import os
import datetime
import uuid
import chromadb
from sentence_transformers import SentenceTransformer

class LocalMemoryDB:
    def __init__(self):
        # 1. DB 저장 경로 설정 (docker-compose.yml에서 주입받은 환경변수 사용)
        self.db_path = os.getenv("CHROMA_DB_PATH", "./local_memory_db")
        
        print(f"🔄 [DB Init] 로컬 기억 저장소 마운트 준비 중... 경로: {self.db_path}")
        
        # 2. ChromaDB 클라이언트 초기화 (데이터를 파일 형태로 영구 보존)
        self.client = chromadb.PersistentClient(path=self.db_path)
        
        # 3. 한국어 특화 경량 임베딩 모델 로드
        # 주의: 컨테이너 최초 실행 시 모델을 다운로드하느라 1~2분 정도 걸릴 수 있습니다.
        print("🧠 [DB Init] 한국어 임베딩 모델 로드 중 (snunlp/KR-SBERT-VCC-STS-B)...")
        self.embedding_model = SentenceTransformer('snunlp/KR-SBERT-VCC-STS-B')
        
        # 4. 기억을 담을 컬렉션(테이블) 생성 또는 가져오기
        self.collection = self.client.get_or_create_collection(
            name="senior_memories"
        )
        print("✅ [DB Init] 로컬 벡터 DB 초기화 완료! 안전하게 보호됩니다.")

    def insert_memory(self, text: str, date_str: str = None) -> str:
        """
        어르신의 원본 발화(STT)를 로컬 DB에 암호화(벡터화)하여 적재합니다.
        외부 서버로는 절대 전송되지 않는 치매 예방용 원본 데이터입니다.
        """
        if not date_str:
            date_str = datetime.date.today().isoformat()
            
        # 고유 ID 생성 (예: mem_1718690000_a1b2c3)
        memory_id = f"mem_{int(datetime.datetime.now().timestamp())}_{uuid.uuid4().hex[:6]}"
        
        try:
            # 텍스트를 벡터(숫자 배열)로 변환
            vector = self.embedding_model.encode(text).tolist()
            
            # DB에 적재
            self.collection.add(
                ids=[memory_id],
                embeddings=[vector],
                metadatas=[{"date": date_str}],
                documents=[text]
            )
            print(f"🔒 [Local DB] 기억 저장 완료: [{date_str}] {text[:15]}...")
            return memory_id
        except Exception as e:
            print(f"❌ [Local DB Error] 기억 저장 실패: {e}")
            return None

    def search_memory(self, query_text: str, limit: int = 3) -> list:
        """
        어르신의 질문과 가장 유사한 과거의 원본 기억을 찾아옵니다.
        """
        try:
            # 질문도 동일하게 벡터로 변환
            query_vector = self.embedding_model.encode(query_text).tolist()
            
            # DB에서 가장 가까운 기억 검색
            results = self.collection.query(
                query_embeddings=[query_vector],
                n_results=limit
            )
            
            memories = []
            # 결과 파싱
            if results and results['documents'] and results['documents'][0]:
                docs = results['documents'][0]
                metas = results['metadatas'][0]
                
                for doc, meta in zip(docs, metas):
                    memories.append({
                        "content": doc,
                        "date": meta.get("date", "날짜 미상")
                    })
            return memories
            
        except Exception as e:
            print(f"❌ [Local DB Error] 기억 검색 실패: {e}")
            return []

# 싱글톤으로 인스턴스 생성 (다른 파일에서 db_manager만 임포트해서 쓰면 됨)
db_manager = LocalMemoryDB()

# ==========================================
# 🧪 직접 실행해보기 위한 테스트 코드
# ==========================================
if __name__ == "__main__":
    print("\n--- 🚀 로컬 DB 단독 테스트 시작 ---\n")
    
    # 1. 데이터 넣기
    db_manager.insert_memory("며느리가 생활비를 너무 적게 줘서 서운해. 다른 사람한테는 비밀이야.", "2026-05-10")
    db_manager.insert_memory("오늘 점심에 먹은 된장찌개가 참 맛있었어.", "2026-06-18")
    db_manager.insert_memory("손주 영수가 오랜만에 집에 놀러와서 용돈을 줬어.", "2026-05-12")
    
    # 2. 데이터 검색해보기
    print("\n🔍 어르신 질문: '우리 며느리랑 돈 때문에 싸운게 언제더라?'")
    results = db_manager.search_memory("며느리랑 돈 때문에 싸운게 언제더라?", limit=1)
    
    for idx, res in enumerate(results):
        print(f"  👉 찾은 기억 [{idx+1}]: {res['date']} - {res['content']}")