# services/ad_fetcher.py — Reklam platformlarından veri çekme
import os
from datetime import datetime, timedelta
from loguru import logger


# ─────────────────────────────
# META ADS
# ─────────────────────────────
class MetaAdsFetcher:
    def __init__(self):
        from facebook_business.api import FacebookAdsApi
        from facebook_business.adobjects.adaccount import AdAccount

        FacebookAdsApi.init(
            app_id=os.getenv("META_APP_ID"),
            app_secret=os.getenv("META_APP_SECRET"),
            access_token=os.getenv("META_ACCESS_TOKEN"),
        )
        self.AdAccount = AdAccount

    def get_account_metrics(self, ad_account_id: str, days: int = 7) -> dict:
        """Son N günün toplam metriklerini çeker."""
        try:
            account = self.AdAccount(f"act_{ad_account_id}")
            since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            until = datetime.now().strftime("%Y-%m-%d")

            insights = account.get_insights(params={
                "time_range": {"since": since, "until": until},
                "fields": [
                    "spend", "impressions", "clicks",
                    "actions", "action_values", "ctr", "cpc"
                ],
                "level": "account",
            })

            if not insights:
                return {}

            data = insights[0]
            conversions = sum(
                int(a["value"]) for a in data.get("actions", [])
                if a["action_type"] in ("purchase", "lead", "complete_registration")
            )
            revenue = sum(
                float(a["value"]) for a in data.get("action_values", [])
                if a["action_type"] == "purchase"
            )
            spend = float(data.get("spend", 0))

            return {
                "platform": "meta",
                "spend": spend,
                "impressions": int(data.get("impressions", 0)),
                "clicks": int(data.get("clicks", 0)),
                "conversions": conversions,
                "revenue": revenue,
                "roas": round(revenue / spend, 2) if spend > 0 else 0,
                "ctr": float(data.get("ctr", 0)),
                "cpc": float(data.get("cpc", 0)),
                "period_days": days,
            }
        except Exception as e:
            logger.error(f"Meta veri çekme hatası ({ad_account_id}): {e}")
            return {}

    def get_campaign_list(self, ad_account_id: str) -> list:
        """Aktif kampanya listesini döner."""
        try:
            account = self.AdAccount(f"act_{ad_account_id}")
            campaigns = account.get_campaigns(fields=["id", "name", "status", "daily_budget"])
            return [
                {
                    "external_id": c["id"],
                    "name": c["name"],
                    "status": c["status"].lower(),
                    "budget_daily": float(c.get("daily_budget", 0)) / 100,
                }
                for c in campaigns
            ]
        except Exception as e:
            logger.error(f"Meta kampanya listesi hatası: {e}")
            return []


# ─────────────────────────────
# GOOGLE ADS
# ─────────────────────────────
class GoogleAdsFetcher:
    def __init__(self):
        from google.ads.googleads.client import GoogleAdsClient

        self.client = GoogleAdsClient.load_from_dict({
            "developer_token": os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN"),
            "client_id": os.getenv("GOOGLE_ADS_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_ADS_CLIENT_SECRET"),
            "refresh_token": os.getenv("GOOGLE_ADS_REFRESH_TOKEN"),
            "login_customer_id": os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID"),
            "use_proto_plus": True,
        })

    def get_account_metrics(self, customer_id: str, days: int = 7) -> dict:
        """Son N günün Google Ads metriklerini çeker."""
        try:
            service = self.client.get_service("GoogleAdsService")
            since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            until = datetime.now().strftime("%Y-%m-%d")

            query = f"""
                SELECT
                    metrics.cost_micros,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.conversions,
                    metrics.conversions_value,
                    metrics.ctr,
                    metrics.average_cpc
                FROM customer
                WHERE segments.date BETWEEN '{since}' AND '{until}'
            """

            response = service.search(customer_id=customer_id, query=query)
            spend = impressions = clicks = conversions = revenue = 0

            for row in response:
                m = row.metrics
                spend += m.cost_micros / 1_000_000
                impressions += m.impressions
                clicks += m.clicks
                conversions += m.conversions
                revenue += m.conversions_value

            return {
                "platform": "google",
                "spend": round(spend, 2),
                "impressions": impressions,
                "clicks": clicks,
                "conversions": int(conversions),
                "revenue": round(revenue, 2),
                "roas": round(revenue / spend, 2) if spend > 0 else 0,
                "ctr": round((clicks / impressions * 100), 2) if impressions > 0 else 0,
                "cpc": round(spend / clicks, 2) if clicks > 0 else 0,
                "period_days": days,
            }
        except Exception as e:
            logger.error(f"Google Ads veri çekme hatası ({customer_id}): {e}")
            return {}
