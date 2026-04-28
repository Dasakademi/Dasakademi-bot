# models.py — Veritabani modelleri
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(200))
    phone = Column(String(50))
    status = Column(String(20), default="active")  # active, paused, churned

    # Platform hesap ID'leri
    meta_ad_account_id = Column(String(50))
    google_customer_id = Column(String(50))

    monthly_budget = Column(Float, default=0)
    notes = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    campaigns = relationship("Campaign", back_populates="client")
    reports = relationship("DailyReport", back_populates="client")
    tasks = relationship("Task", back_populates="client")


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    name = Column(String(200))
    platform = Column(String(20))  # meta, google, email, whatsapp
    external_id = Column(String(100))  # platform'daki ID
    status = Column(String(20))  # active, paused, ended
    budget_daily = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client", back_populates="campaigns")
    metrics = relationship("CampaignMetric", back_populates="campaign")


class CampaignMetric(Base):
    __tablename__ = "campaign_metrics"

    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"))
    date = Column(DateTime)
    spend = Column(Float, default=0)
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    conversions = Column(Integer, default=0)
    revenue = Column(Float, default=0)
    roas = Column(Float, default=0)
    ctr = Column(Float, default=0)
    cpc = Column(Float, default=0)
    fetched_at = Column(DateTime, default=datetime.utcnow)

    campaign = relationship("Campaign", back_populates="metrics")


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    report_date = Column(DateTime)
    summary = Column(Text)       # AI tarafından üretilen özet
    alerts = Column(Text)        # Uyarılar (JSON string)
    recommendations = Column(Text)  # AI önerileri
    total_spend = Column(Float, default=0)
    total_revenue = Column(Float, default=0)
    avg_roas = Column(Float, default=0)
    sent_at = Column(DateTime)

    client = relationship("Client", back_populates="reports")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    title = Column(String(300))
    description = Column(Text)
    priority = Column(String(20), default="normal")  # urgent, high, normal, low
    status = Column(String(20), default="pending")   # pending, done, snoozed
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    client = relationship("Client", back_populates="tasks")


class AlertLog(Base):
    __tablename__ = "alert_logs"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    alert_type = Column(String(50))   # budget_low, roas_drop, conversion_drop vs.
    message = Column(Text)
    severity = Column(String(20))     # info, warning, critical
    is_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
