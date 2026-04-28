# services/scheduler.py — Otomatik zamanlayıcı ve Telegram bildirimleri
import os
import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
import telegram


class NotificationService:
    def __init__(self):
        self.bot = telegram.Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")

    async def send(self, message: str, parse_mode: str = "Markdown"):
        """Telegram'a mesaj gönder."""
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=parse_mode
            )
            logger.info("Telegram bildirimi gönderildi")
        except Exception as e:
            logger.error(f"Telegram gönderim hatası: {e}")

    async def send_alert(self, alert: dict):
        """Uyarı bildirimi gönder."""
        emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(alert["severity"], "⚪")
        await self.send(f"{emoji} *UYARI*\n{alert['message']}")

    async def send_daily_report(self, summary: str, report_type: str = "sabah"):
        """Günlük özet rapor gönder."""
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        header = "☀️ *SABAH RAPORU*" if report_type == "sabah" else "🌙 *AKŞAM RAPORU*"
        message = f"{header} — {now}\n\n{summary}"
        await self.send(message)


class SchedulerService:
    def __init__(self, db_session_factory, fetcher_meta, fetcher_google, analyst, notifier):
        self.scheduler = AsyncIOScheduler()
        self.db = db_session_factory
        self.meta = fetcher_meta
        self.google = fetcher_google
        self.analyst = analyst
        self.notifier = notifier

    def start(self):
        morning_hour = int(os.getenv("MORNING_REPORT_HOUR", 8))
        evening_hour = int(os.getenv("EVENING_REPORT_HOUR", 18))

        # Sabah raporu
        self.scheduler.add_job(
            self.run_morning_report,
            CronTrigger(hour=morning_hour, minute=0),
            id="morning_report",
            replace_existing=True,
        )

        # Akşam raporu
        self.scheduler.add_job(
            self.run_evening_report,
            CronTrigger(hour=evening_hour, minute=0),
            id="evening_report",
            replace_existing=True,
        )

        # Her saat uyarı kontrolü
        self.scheduler.add_job(
            self.check_alerts,
            CronTrigger(minute=0),
            id="hourly_alerts",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info(f"Zamanlayıcı başladı — Sabah {morning_hour}:00, Akşam {evening_hour}:00")

    async def run_morning_report(self):
        logger.info("Sabah raporu çalışıyor...")
        try:
            clients_data = await self._fetch_all_clients()
            summary = self.analyst.generate_daily_summary(clients_data)
            await self.notifier.send_daily_report(summary, report_type="sabah")
        except Exception as e:
            logger.error(f"Sabah raporu hatası: {e}")
            await self.notifier.send(f"❗ Sabah raporu oluşturulamadı: {e}")

    async def run_evening_report(self):
        logger.info("Akşam raporu çalışıyor...")
        try:
            clients_data = await self._fetch_all_clients()
            summary = self.analyst.generate_daily_summary(clients_data)
            await self.notifier.send_daily_report(summary, report_type="akşam")
        except Exception as e:
            logger.error(f"Akşam raporu hatası: {e}")

    async def check_alerts(self):
        """Her saat otomatik uyarı kontrolü."""
        try:
            with self.db() as session:
                from models import Client
                clients = session.query(Client).filter_by(status="active").all()

            for client in clients:
                metrics = {}
                if client.meta_ad_account_id:
                    metrics["meta"] = self.meta.get_account_metrics(
                        client.meta_ad_account_id, days=1
                    )
                if client.google_customer_id:
                    metrics["google"] = self.google.get_account_metrics(
                        client.google_customer_id, days=1
                    )

                for platform, data in metrics.items():
                    alerts = self.analyst.detect_alerts(client.name, data, {})
                    for alert in alerts:
                        if alert["severity"] == "critical":
                            await self.notifier.send_alert(alert)

        except Exception as e:
            logger.error(f"Uyarı kontrol hatası: {e}")

    async def _fetch_all_clients(self) -> list:
        """Tüm aktif müşterilerin verilerini toplar."""
        results = []
        with self.db() as session:
            from models import Client
            clients = session.query(Client).filter_by(status="active").all()

        for client in clients:
            data = {"name": client.name, "spend": 0, "roas": 0}
            if client.meta_ad_account_id:
                m = self.meta.get_account_metrics(client.meta_ad_account_id, days=1)
                data["spend"] += m.get("spend", 0)
                data["roas"] = m.get("roas", 0)
            if client.google_customer_id:
                g = self.google.get_account_metrics(client.google_customer_id, days=1)
                data["spend"] += g.get("spend", 0)
                if data["roas"] == 0:
                    data["roas"] = g.get("roas", 0)
            data["status"] = "iyi" if data["roas"] >= 3 else "dikkat"
            results.append(data)

        return results
