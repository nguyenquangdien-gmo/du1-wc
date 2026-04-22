from fastapi import FastAPI
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from alembic.config import Config
from alembic import command
import os

# Load environment variables from Render secrets path if it exists, otherwise from .env
render_secrets_path = "/etc/secrets/.env"
if os.path.exists(render_secrets_path):
    load_dotenv(render_secrets_path)
else:
    load_dotenv()
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from database import engine, Base
from routers import auth, matches, admin, tournament
from services.scheduler import start_scheduler
import os


# Create DB tables (Đã chuyển vào lifespan bên dưới để an toàn hơn)

def mask_value(val: str) -> str:
    if not val: return "[Mất/Trống]"
    if len(val) <= 8: return "****"
    return f"{val[:4]}...{val[-4:]}"

def log_env_status():
    keys = ["APP_URL", "MAIL_USERNAME", "MAIL_PASSWORD", "BREVO_API_KEY", "GEMINI_API_KEY", "SECRET_KEY", "DATABASE_URL"]
    print("--- KIỂM TRA BIẾN MÔI TRƯỜNG ---")
    for key in keys:
        val = os.environ.get(key)
        print(f"{key}: {mask_value(val)}")
    print("-------------------------------")

log_env_status()

from database import engine, Base, models, SessionLocal
from init_data import seed_data

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo database
    print("Application starting... Initializing database & scheduler.")
    
    # Tạo bảng nếu chưa có (chỉ tạo bảng mới, không ảnh hưởng migrate)
    Base.metadata.create_all(bind=engine)
    
    # 2. Tự động seed data nếu DB trống (chưa có user nào)
    db = SessionLocal()
    try:
        user_count = db.query(models.User).count()
        if user_count == 0:
            print("Database is empty. Running initial seed...")
            seed_data()
        else:
            print(f"Database already has {user_count} users. Skipping seed.")
    except Exception as e:
        print(f"Error checking/seeding database: {e}")
    finally:
        db.close()
    
    start_scheduler()
    yield

app = FastAPI(title="World Cup 2026", lifespan=lifespan)

# Include routers
app.include_router(auth.router)
app.include_router(matches.router)
app.include_router(admin.router)
app.include_router(tournament.router)

# Ensure static folder exists
os.makedirs("static", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.get("/")
def serve_frontend():
    return FileResponse("static/index.html")

@app.get("/dashboard")
def serve_dashboard():
    return FileResponse("static/dashboard.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
