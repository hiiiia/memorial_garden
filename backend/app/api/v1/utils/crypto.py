from cryptography.fernet import Fernet
import os

# .env 파일에 저장해둔 32바이트 인코딩 키를 불러옵니다.
# (키 생성 방법: 파이썬 터미널에서 Fernet.generate_key() 실행 후 복사)

from core.config import settings

ENCRYPTION_KEY = os.getenv("DB_ENCRYPTION_KEY", "default-token")

if ENCRYPTION_KEY:
    cipher_suite = Fernet(ENCRYPTION_KEY)
else:
    cipher_suite = None

def encrypt_token(token: str) -> str:
    if not token or not cipher_suite:
        return token
    # 문자열을 바이트로 변환 후 암호화, 다시 DB 저장을 위해 문자열로 변환
    return cipher_suite.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str) -> str:
    if not encrypted_token or not cipher_suite:
        return encrypted_token
    # 복호화 후 다시 원본 문자열로 변환
    return cipher_suite.decrypt(encrypted_token.encode()).decode()