from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

import os
from sqlalchemy.engine import make_url

# Yêu cầu bắt buộc cung cấp DATABASE_URL (MySQL)
raw_url = os.environ.get("DATABASE_URL")
if not raw_url:
    raise ValueError("LỖI: Biến môi trường DATABASE_URL không được thiết lập. Hệ thống yêu cầu MySQL để vận hành.")

# Tự động sửa lỗi Driver nếu user nhập mysql://
if raw_url.startswith("mysql://"):
    raw_url = raw_url.replace("mysql://", "mysql+pymysql://", 1)

# Phân tích URL để loại bỏ các tham số không tương thích (như ssl-mode)
url = make_url(raw_url)

# Render/Aiven thường thêm ?ssl-mode=REQUIRED, pymysql không nhận cái này
query = dict(url.query)
query.pop("ssl-mode", None)
query.pop("ssl_ca", None)

# Tạo lại URL sạch
new_url = url._replace(query=query)

# Cấu hình SSL qua connect_args (pymysql style)
connect_args = {}
db_ssl = os.environ.get("DATABASE_SSL", "false").lower() == "true"
db_ssl_ca = os.environ.get("DATABASE_SSL_CA")

if db_ssl:
    if db_ssl_ca and os.path.exists(db_ssl_ca):
        connect_args["ssl"] = {"ca": db_ssl_ca}
    else:
        connect_args["ssl"] = True

# Cấu hình tối ưu cho MySQL
engine = create_engine(
    new_url,
    connect_args=connect_args,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    pool_pre_ping=True
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
