from datetime import datetime, timedelta
from typing import Optional
import bcrypt
import jwt
import os
import secrets

SECRET_KEY = os.environ.get("SECRET_KEY", "super_secret_key_wc2026_change_in_production")
ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 days

# Không còn dùng passlib do lỗi tương thích Python 3.12+
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        # Bcrypt yêu cầu đầu vào là bytes
        password_bytes = plain_password.encode('utf-8')
        # Bcrypt có giới hạn vật lý 72 bytes
        password_bytes = password_bytes[:72]
        
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception as e:
        print(f"Bcrypt verification error: {e}")
        return False

def get_password_hash(password: str) -> str:
    # Bcrypt yêu cầu đầu vào là bytes
    password_bytes = password.encode('utf-8')
    # Cắt ngắn 72 bytes để đảm bảo tính tương thích
    password_bytes = password_bytes[:72]
    
    # Tạo salt và hash
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def generate_otp():
    return "".join(str(secrets.randbelow(10)) for _ in range(6))
