from fastapi import FastAPI
from contextlib import asynccontextmanager
from dotenv import load_dotenv
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
from routers import auth, matches, admin
from services.scheduler import start_scheduler
import os

# Create DB tables
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Application starting... Initializing scheduler.")
    start_scheduler()
    yield

app = FastAPI(title="World Cup 2026 Betting", lifespan=lifespan)

# Include routers
app.include_router(auth.router)
app.include_router(matches.router)
app.include_router(admin.router)

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
