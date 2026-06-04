# app/utils/security.py

import os
import bcrypt
from cryptography.fernet import Fernet
from passlib.context import CryptContext
from core.config import settings


# ==========================================
# 1. 양방향 암호화 (카카오 토큰용 - Fernet)
# ==========================================

# .env 파일에 저장해둔 32바이트 인코딩 키를 불러옵니다.
# (키 생성 방법: 파이썬 터미널에서 Fernet.generate_key() 실행 후 복사)
# .env에서 키를 가져오되, 없으면 서버가 죽지 않도록 임시 전용 키를 즉석에서 생성(서버 다운 방지)
raw_key = os.getenv("DB_ENCRYPTION_KEY")
ENCRYPTION_KEY = raw_key if raw_key else Fernet.generate_key().decode()
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

# ==========================================
# 2. 단방향 해싱 (비밀번호용 - bcrypt)
# ==========================================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    # 문자열을 바이트로 변환 후 솔트(salt)를 섞어 해싱하고 다시 문자열로 반환
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        # 입력된 비밀번호와 DB의 해시를 비교
        return bcrypt.checkpw(
            plain_password.encode('utf-8'), 
            hashed_password.encode('utf-8')
        )
    except Exception:
        # 72바이트 초과 등의 에러가 나면 무조건 False 반환 (서버 다운 방지)
        return False