# main.py — FastAPI ana uygulama (Railway uyumlu)
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from loguru import logger

load_dotenv()

# Railway bazen değişken isimlerini çeviriyor, ikisini de destekle
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_SOHBET_ID")
MORNING_HOUR = int(os.getenv("MORNING_REPORT_HOUR") or os.getenv("SABAH_RAPORU_SAATI") or 8)
MORNING_MIN = int(os.getenv("MORNING_REPORT_MINUTE") or os.getenv("SABAH_RAPORU_DAKIKA") or 0)
EVENING_HOUR = int(os.getenv("EVENING_REPORT_HOUR") or os.getenv("AKSAM_RAPORU_SAATI") or 18)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ajans.db")

from models import Base, Client, Task

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Ajans sistemi baslatildi")
    if ANTHROPIC_API_KEY and TELEGRAM_BOT_TOKEN:
        try:
            from services.scheduler import SchedulerService, NotificationService
            from services.ad_fetcher import MetaAdsFetcher, GoogleAdsFetcher
            from services.ai_analyst import AIAnalyst
            notifier = NotificationService()
            analyst = AIAnalyst()
            meta = MetaAdsFetcher()
            google = GoogleAdsFetcher()
            scheduler = SchedulerService(SessionLocal, meta, google, analyst, notifier)
            scheduler.start()
            app.state.scheduler = scheduler
            logger.info("Zamanlayi baslatildi")
        except Exception as e:
            logger.warning(f"Zamanlayi baslatılamadi: {e}")
    else:
        logger.warning("API anahtarlari eksik — zamanlayi devre disi")
    yield

app = FastAPI(title="Ajans Otomasyon API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
def health():
    from datetime import datetime
    return {
        "status": "ok",
        "time": str(datetime.now()),
        "anthropic_bagli": bool(ANTHROPIC_API_KEY),
        "telegram_bagli": bool(TELEGRAM_BOT_TOKEN),
    }

@app.get("/clients")
def list_clients(db: Session = Depends(get_db)):
    return db.query(Client).filter_by(status="active").all()

@app.post("/clients")
def create_client(data: dict, db: Session = Depends(get_db)):
    client = Client(**data)
    db.add(client)
    db.commit()
    db.refresh(client)
    return client

@app.get("/clients/{client_id}")
def get_client(client_id: int, db: Session = Depends(get_db)):
    client = db.query(Client).filter_by(id=client_id).first()
    if not client:
        raise HTTPException(404, "Musteri bulunamadi")
    return client

@app.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    clients = db.query(Client).filter_by(status="active").all()
    tasks = db.query(Task).filter_by(status="pending").all()
    return {
        "toplam_musteri": len(clients),
        "bekleyen_gorev": len(tasks),
        "acil_gorev": len([t for t in tasks if t.priority == "urgent"]),
    }

@app.get("/tasks")
def list_tasks(db: Session = Depends(get_db)):
    return db.query(Task).filter_by(status="pending").all()

@app.post("/tasks/{task_id}/complete")
def complete_task(task_id: int, db: Session = Depends(get_db)):
    from datetime import datetime
    task = db.query(Task).filter_by(id=task_id).first()
    if not task:
        raise HTTPException(404, "Gorev bulunamadi")
    task.status = "done"
    task.completed_at = datetime.utcnow()
    db.commit()
    return {"status": "Tamamlandi"}
