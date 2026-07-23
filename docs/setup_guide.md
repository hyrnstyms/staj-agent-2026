# Asistan — Kurulum Rehberi

## Ön Gereksinimler

| Yazılım | Versiyon | Not |
|---|---|---|
| Python | 3.11+ | Backend |
| Node.js | 18+ | Frontend |
| Ollama | Latest | LLM runtime |
| Docker | Latest | n8n + sandbox için |
| Rust | Latest | Tauri masaüstü uygulaması için (opsiyonel) |

## 1. Ollama Kurulumu

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Model çek
ollama pull qwen2.5:3b-instruct

# (Opsiyonel) Vision modeli
ollama pull qwen2-vl
```

## 2. Backend Kurulumu

```bash
cd backend

# Python sanal ortam
python3 -m venv venv
source venv/bin/activate     # macOS/Linux
# venv\Scripts\activate      # Windows

# Bağımlılıklar
pip install -r requirements.txt
pip install python-multipart  # Dosya yükleme için

# Ortam değişkenleri
cp .env.example .env
# .env dosyasını düzenleyin (API key, sandbox path vb.)

# Veritabanı seed (demo veriler)
python -c "from db.seed import seed_database; seed_database()"

# Backend başlat
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 1 --reload
```

> ⚠️ **`--workers 1` zorunludur!** In-memory state (onay, oturum) birden fazla worker'da çalışmaz.

## 3. Frontend (Desktop App) Kurulumu

```bash
cd desktop-app

# Node paketleri
npm install

# Geliştirme sunucusu (tarayıcıda test)
npm run dev
# → http://localhost:1420/

# Tauri masaüstü uygulaması (Rust gerektirir)
npm run tauri dev
```

## 4. n8n Kurulumu (Mail/Takvim için)

```bash
# docker-compose ile başlat
docker-compose up -d n8n

# n8n arayüzü: http://localhost:5678
# İlk girişte kullanıcı adı/şifre belirleyin
```

### Gmail OAuth Bağlantısı
1. [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Enable APIs → **Gmail API**
2. Credentials → Create Credentials → OAuth Client ID → Web Application
3. Authorized redirect URI: `http://localhost:5678/rest/oauth2-credential/callback`
4. n8n → Credentials → Add → Gmail OAuth2 → Client ID/Secret yapıştır → Connect

### Google Calendar OAuth
1. Google Cloud Console → Enable APIs → **Google Calendar API**
2. Aynı OAuth Client ID kullanılabilir
3. n8n → Add Credential → Google Calendar OAuth2 → Aynı adımlar

### Workflow'ları Yükle
1. n8n → Workflows → Import from file
2. `n8n/workflows/mail_workflow.json` yükle → Activate
3. `n8n/workflows/calendar_workflow.json` yükle → Activate
4. `.env`'e ekle: `N8N_WEBHOOK_URL=http://localhost:5678/webhook/agent`

## 5. Docker ile Tüm Servisleri Başlatma

```bash
# Tüm servisleri başlat (ollama + backend + n8n)
docker-compose up -d

# Ollama modelini çek (ilk kurulumda)
docker-compose exec ollama ollama pull qwen2.5:3b-instruct
```

## 6. Test

```bash
# Sağlık kontrolü
curl http://localhost:8000/health

# Terminal istemcisi
cd backend && python test_chat.py

# MCP tool listesi
curl -H "X-API-Key: dev-api-key-change-in-production" http://localhost:8000/mcp/tools

# Swagger arayüzü
# Tarayıcıda: http://localhost:8000/docs
```

## Portlar

| Servis | Port | Açıklama |
|---|---|---|
| Backend API | 8000 | FastAPI (REST + WebSocket + MCP) |
| Frontend Dev | 1420 | Vite dev server |
| Ollama | 11434 | LLM runtime |
| n8n | 5678 | Otomasyon/OAuth |
