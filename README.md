# Ajans Otomasyon Sistemi

## Proje yapısı

```
/opt/ajans/
├── main.py                  ← FastAPI ana uygulama
├── models.py                ← Veritabanı modelleri
├── .env                     ← API anahtarları (gizli!)
├── services/
│   ├── ad_fetcher.py        ← Meta + Google Ads veri çekme
│   ├── ai_analyst.py        ← Claude API analiz motoru
│   └── scheduler.py        ← Zamanlayıcı + Telegram bildirimleri
└── venv/                    ← Python sanal ortam
```

---

## Kurulum adımları

### 1. Sunucuya bağlan ve scripti çalıştır
```bash
ssh root@SUNUCU_IP
curl -o setup.sh https://...  # veya dosyayı manuel kopyala
chmod +x setup.sh
bash setup.sh
```

### 2. Proje dosyalarını kopyala
```bash
cd /opt/ajans
# main.py, models.py, services/ klasörünü buraya kopyala
```

### 3. .env dosyasını oluştur
```bash
cp .env.example .env
nano .env   # API anahtarlarını gir
```

### 4. Telegram bot kur (5 dakika)
1. Telegram'da @BotFather'a yaz → /newbot
2. Bot adı ve username ver
3. Token'ı .env içine TELEGRAM_BOT_TOKEN'a yaz
4. Bota bir mesaj at, sonra şunu çalıştır:
   https://api.telegram.org/botTOKEN/getUpdates
5. chat.id değerini TELEGRAM_CHAT_ID'ye yaz

### 5. Sistemi başlat
```bash
source venv/bin/activate
supervisorctl start ajans
supervisorctl status
```

### 6. Test et
```bash
curl http://localhost:8000/health
# {"status": "ok", ...} görmelisin

# Manuel rapor tetikle
curl -X POST http://localhost:8000/reports/daily
```

---

## Günlük kullanım

Sistem otomatik çalışır. Her sabah 08:00 ve akşam 18:00'de
Telegram'a rapor gelir. Her saat kritik uyarı kontrolü yapılır.

Manuel analiz için:
```bash
# Belirli müşteri analizi
curl http://localhost:8000/clients/1/analyze -X POST

# Dashboard özeti
curl http://localhost:8000/dashboard/summary
```

---

## Sorun giderme

```bash
# Logları izle
tail -f /var/log/ajans_out.log
tail -f /var/log/ajans_err.log

# Servisi yeniden başlat
supervisorctl restart ajans
```
