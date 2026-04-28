# main.py — FastAPI ana uygulama
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from loguru import logger

load_dotenv()

from models import Base, Client, Campaign, CampaignMetric, DailyReport, Task, AlertLog
from services.ad_fetcher import MetaAdsFetcher, GoogleAdsFetcher
from services.ai_analyst import AIAnalyst
from services.scheduler import SchedulerService, NotificationService

# ─── Veritabanı ───
engine = create_engine(os.getenv("DATABASE_URL"))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ─── Servisler ───
meta_fetcher = MetaAdsFetcher()
google_fetcher = GoogleAdsFetcher()
analyst = AIAnalyst()
notifier = NotificationService()
scheduler_svc = SchedulerService(
    db_session_factory=SessionLocal,
    fetcher_meta=meta_fetcher,
    fetcher_google=google_fetcher,
    analyst=analyst,
    notifier=notifier,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler_svc.start()
    logger.info("Ajans sistemi başlatıldı")
    yield
    scheduler_svc.scheduler.shutdown()

app = FastAPI(title="Ajans Otomasyon API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Müşteri Endpoint'leri ───

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
        raise HTTPException(status_code=404, detail="Müşteri bulunamadı")
    return client

# ─── Dashboard Endpoint'leri ───

@app.get("/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db)):
    """Dashboard için özet veri."""
    clients = db.query(Client).filter_by(status="active").all()
    tasks = db.query(Task).filter_by(status="pending").all()
    urgent_tasks = [t for t in tasks if t.priority == "urgent"]
    alerts = db.query(AlertLog).filter_by(is_sent=False).all()

    return {
        "total_clients": len(clients),
        "pending_tasks": len(tasks),
        "urgent_tasks": len(urgent_tasks),
        "new_alerts": len(alerts),
    }

@app.get("/clients/{client_id}/metrics")
def get_client_metrics(client_id: int, days: int = 7, db: Session = Depends(get_db)):
    """Müşterinin reklam metriklerini çeker (canlı veri)."""
    client = db.query(Client).filter_by(id=client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Müşteri bulunamadı")

    metrics = {}
    if client.meta_ad_account_id:
        metrics["meta"] = meta_fetcher.get_account_metrics(client.meta_ad_account_id, days)
    if client.google_customer_id:
        metrics["google"] = google_fetcher.get_account_metrics(client.google_customer_id, days)

    return metrics

@app.post("/clients/{client_id}/analyze")
def analyze_client(client_id: int, db: Session = Depends(get_db)):
    """Claude AI ile müşteri analizi yapar."""
    client = db.query(Client).filter_by(id=client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Müşteri bulunamadı")

    metrics = {}
    if client.meta_ad_account_id:
        metrics["meta"] = meta_fetcher.get_account_metrics(client.meta_ad_account_id, days=7)
    if client.google_customer_id:
        metrics["google"] = google_fetcher.get_account_metrics(client.google_customer_id, days=7)

    result = analyst.analyze_client(client.name, metrics)
    return result

@app.post("/reports/daily")
async def trigger_daily_report():
    """Manuel olarak günlük raporu tetikler."""
    await scheduler_svc.run_morning_report()
    return {"status": "Rapor gönderildi"}

# ─── Görev Endpoint'leri ───

@app.get("/tasks")
def list_tasks(db: Session = Depends(get_db)):
    return db.query(Task).filter_by(status="pending").order_by(Task.priority).all()

@app.post("/tasks/{task_id}/complete")
def complete_task(task_id: int, db: Session = Depends(get_db)):
    from datetime import datetime
    task = db.query(Task).filter_by(id=task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Görev bulunamadı")
    task.status = "done"
    task.completed_at = datetime.utcnow()
    db.commit()
    return {"status": "Görev tamamlandı"}

@app.get("/health")
def health():
    return {"status": "ok", "time": str(__import__("datetime").datetime.now())}
