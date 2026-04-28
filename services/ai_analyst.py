# services/ai_analyst.py — Claude API ile analiz ve öneri üretimi
import anthropic
from loguru import logger


class AIAnalyst:
    def __init__(self):
        self.client = anthropic.Anthropic()
        self.model = "claude-sonnet-4-20250514"

    def analyze_client(self, client_name: str, metrics: dict) -> dict:
        """
        Bir müşterinin metriklerini analiz eder,
        uyarılar ve öneriler üretir.
        """
        try:
            prompt = f"""
Sen bir dijital pazarlama uzmanısın. Aşağıdaki müşteri reklam verilerini analiz et.

Müşteri: {client_name}

Meta Ads verileri (son 7 gün):
{_format_metrics(metrics.get("meta", {}))}

Google Ads verileri (son 7 gün):
{_format_metrics(metrics.get("google", {}))}

Şunları ver:
1. DURUM: Genel performans değerlendirmesi (1-2 cümle)
2. UYARILAR: Dikkat gerektiren durumlar (varsa, madde madde)
3. ÖNERİLER: Bu hafta yapılması gereken 2-3 somut aksiyon
4. SKOR: 1-10 arası performans skoru

Türkçe, kısa ve net yaz. Ajans sahibi için, teknik değil pratik bilgi ver.
"""
            message = self.client.messages.create(
                model=self.model,
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}]
            )
            return {
                "analysis": message.content[0].text,
                "tokens_used": message.usage.input_tokens + message.usage.output_tokens,
            }
        except Exception as e:
            logger.error(f"AI analiz hatası ({client_name}): {e}")
            return {"analysis": "Analiz yapılamadı.", "tokens_used": 0}

    def generate_daily_summary(self, all_clients_data: list) -> str:
        """
        Tüm müşterilerin verilerinden günlük özet rapor üretir.
        Sabah ve akşam bildirimi için kullanılır.
        """
        try:
            clients_text = ""
            for c in all_clients_data:
                clients_text += f"\n- {c['name']}: ROAS {c.get('roas', 0):.1f}x, "
                clients_text += f"Harcama {c.get('spend', 0):.0f}₺, "
                clients_text += f"Durum: {c.get('status', 'bilinmiyor')}"

            prompt = f"""
Ajans yöneticisi için günlük özet rapor yaz. Tek kişilik ajans, 10 müşteri.

Müşteri verileri:{clients_text}

Şunları içersin:
1. Bugünün genel durumu (1-2 cümle)
2. Acil dikkat gerektiren müşteri varsa vurgula
3. Bugün yapılması gereken en önemli 3 görev
4. Pozitif bir gelişme varsa belirt

Kısa tut — maksimum 200 kelime. Telegram bildirimi olarak gönderilecek.
"""
            message = self.client.messages.create(
                model=self.model,
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text
        except Exception as e:
            logger.error(f"Günlük özet hatası: {e}")
            return "Günlük özet oluşturulamadı."

    def detect_alerts(self, client_name: str, current: dict, previous: dict) -> list:
        """
        Önceki dönemle karşılaştırarak otomatik uyarı üretir.
        Kural tabanlı — AI token harcamaz.
        """
        alerts = []

        # ROAS düşüşü
        if previous.get("roas", 0) > 0:
            roas_change = (current.get("roas", 0) - previous["roas"]) / previous["roas"] * 100
            if roas_change < -20:
                alerts.append({
                    "type": "roas_drop",
                    "severity": "critical",
                    "message": f"{client_name}: ROAS %{abs(roas_change):.0f} düştü "
                               f"({previous['roas']:.1f}x → {current.get('roas', 0):.1f}x)"
                })

        # Bütçe tükenme
        budget = current.get("daily_budget", 0)
        spend = current.get("spend_today", 0)
        if budget > 0 and spend / budget > 0.85:
            alerts.append({
                "type": "budget_high",
                "severity": "warning",
                "message": f"{client_name}: Günlük bütçenin %{spend/budget*100:.0f}'ı harcandı"
            })

        # Dönüşüm sıfır
        if current.get("clicks", 0) > 50 and current.get("conversions", 0) == 0:
            alerts.append({
                "type": "zero_conversion",
                "severity": "critical",
                "message": f"{client_name}: {current['clicks']} tıklama var ama sıfır dönüşüm"
            })

        return alerts


def _format_metrics(m: dict) -> str:
    if not m:
        return "Veri yok"
    return (
        f"Harcama: {m.get('spend', 0):.2f}₺ | "
        f"ROAS: {m.get('roas', 0):.2f}x | "
        f"Tıklama: {m.get('clicks', 0)} | "
        f"Dönüşüm: {m.get('conversions', 0)} | "
        f"CTR: %{m.get('ctr', 0):.2f}"
    )
