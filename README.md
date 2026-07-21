# Asistan — Yerel AI Asistanı

> **Staj Bitirme Projesi** · Faz 0, 1, 2 ve 3 tamamlandı

Yerel (self-hosted) çalışan, Ollama üzerinde Qwen2.5 modeli kullanan,
dosya sistemi / veritabanı / kod / mail / takvim erişimli,
onay mekanizmalı ve tam loglu bir **tool-calling AI asistanı**.

---

## Hızlı Başlangıç

### 1. Ollama Kur ve Modeli İndir

```bash
# Windows — Ollama installer:
# https://ollama.com/download/windows

# Model indir (ilk kurulumda ~2GB)
ollama pull qwen2.5:3b-instruct

# Çalıştığını doğrula
ollama list
```

### 2. Ortam Dosyasını Hazırla

```bash
cd local-agent/backend
cp .env.example .env

# .env dosyasını düzenle:
# - API_KEY: güçlü bir değer seç
# - OLLAMA_BASE_URL: Ollama'nın adresi (varsayılan: http://localhost:11434)
# - SANDBOX_ROOT: dosya işlemlerinin yapılacağı güvenli dizin
```

### 3. Python Ortamı Kur

```bash
cd local-agent/backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 4. Veritabanını Başlat ve Demo Verilerini Yükle

```bash
cd local-agent/backend
python -m db.seed
```

### 5. Backend'i Başlat

```bash
# ⚠️ --workers 1 ZORUNLU — in-memory state nedeniyle
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 1 --reload
```

Backend http://localhost:8000 adresinde hazır.
Swagger UI: http://localhost:8000/docs

---

## Docker ile Başlatma (Önerilen)

```bash
cd local-agent

# İlk kurulum: Ollama modeli indir
docker-compose up ollama -d
docker-compose exec ollama ollama pull qwen2.5:3b-instruct

# Tüm sistemi başlat
docker-compose up -d

# Logları izle
docker-compose logs -f backend
```

---

## Örnek Kullanım

### Dosya okuma (onay gerekmez)

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key-change-in-production" \
  -d '{"message": "README.md dosyasını oku", "session_id": "demo-1"}'
```

### Dosya silme (onay gerektirir)

```bash
# 1. İsteği gönder → approval_id döner
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key-change-in-production" \
  -d '{"message": "notlar.txt dosyasını sil", "session_id": "demo-1"}'

# Yanıt:
# {"status": "pending_approval", "approval_id": "uuid-here", ...}

# 2. Onayla
curl -X POST http://localhost:8000/approve/{approval_id} \
  -H "X-API-Key: dev-api-key-change-in-production"

# 3. Onaylanan işlemi çalıştır
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key-change-in-production" \
  -d '{"message": "notlar.txt dosyasını sil", "session_id": "demo-1", "approval_id": "uuid-here"}'
```

### İnsan Kaynakları — İzin Bakiyesi (Faz 2)

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key-change-in-production" \
  -H "X-User-Role: hr" \
  -H "X-User-Name: Ayşe Kaya" \
  -d '{"message": "Can Öztürk\u0027ün izin bakiyesi nedir?", "session_id": "demo-hr"}'
```

### Güvenli Kod Çalıştırma — Docker Sandbox (Faz 3)

```bash
# Önce sandbox dizininde bir python dosyası oluşturduğunuzu varsayalım
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key-change-in-production" \
  -H "X-User-Role: admin" \
  -d '{"message": "sandbox içerisindeki test.py dosyasını çalıştır", "session_id": "demo-code"}'
```

### WebSocket (streaming)

```javascript
const ws = new WebSocket(
  "ws://localhost:8000/ws/chat?session_id=demo-ws&api_key=dev-api-key-change-in-production"
);
ws.onmessage = (e) => console.log(JSON.parse(e.data));
ws.send(JSON.stringify({ message: "Merhaba, sandbox'ta hangi dosyalar var?" }));
```

---

## Testleri Çalıştır

```bash
cd local-agent/backend

# Tüm testler (LLM gerektirmeyenler)
pytest tests/test_permissions.py tests/test_tools/ -v

# Doğruluk testi (Ollama ile)
pytest tests/test_tool_calling_accuracy.py -v -s

# Doğruluk testi (Ollama olmadan — mock)
MOCK_ROUTER=1 pytest tests/test_tool_calling_accuracy.py -v -s

# Coverage raporu
pytest tests/ --cov=. --cov-report=term-missing
```

---

## ⚠️ Kritik Uyarılar

### Faz 1 Geçici Auth
Tüm API istekleri `X-API-Key` header'ı ile doğrulanır.
`user_id` request body'sinden değil, bu header'dan türetilir.
**Bu geçici bir mekanizmadır — production'da JWT tabanlı auth kullanılmalıdır.**

### Tek Worker Zorunlu
`pending_approvals` ve `ConversationMemory` in-memory tutulduğu için
uvicorn **`--workers 1`** ile çalıştırılmalıdır.
Birden fazla worker olursa onay isteği farklı worker'a düşebilir.
Redis/DB entegrasyonu tamamlanana kadar bu kısıt geçerlidir.

### Sandbox Güvenliği
Dosya işlemleri yalnızca `SANDBOX_ROOT` dizini altında çalışır.
`../../etc/passwd` gibi path traversal girişimleri reddedilir.

---

## Proje Yapısı

```
local-agent/
├── backend/
│   ├── core/          # Agent, Router, Executor, Approval, Memory, Permissions, Logger
│   ├── mcp_servers/   # Filesystem (tam), DB/Code/App (stub)
│   ├── integrations/  # Mail/Takvim/GitHub (stub, Faz 3-4)
│   ├── multimodal/    # STT/TTS/Vision/SD (stub, Faz 6)
│   ├── db/            # SQLAlchemy modelleri, seed verisi
│   ├── api/           # FastAPI app + WebSocket
│   └── tests/         # Doğruluk + izin + dosya sistem testleri
├── docker-compose.yml  # Ollama + Backend (n8n/Postgres yorum satırında)
└── docs/              # Mimari, tool listesi, kurulum, güvenlik
```

---

## Geliştirme Fazları

| Faz | Kapsam | Durum |
|-----|--------|-------|
| 0   | Temel altyapı, config, DB | ✅ Tamamlandı |
| 1   | Agent core, router, onay, RBAC, loglama, filesystem | ✅ Tamamlandı |
| 2   | DB server (tam) + HR senaryosu (RBAC, Parametreli Sorgu) | ✅ Tamamlandı |
| 3   | Docker sandbox + Kod/Git (Command Injection Koruması, Strict İzolasyon) | ✅ Tamamlandı |
| 4   | Mail + Takvim (n8n) | ⏳ Sonraki |
| 5   | Uygulama kontrolü | ⏳ |
| 6   | Whisper + Piper + Vision + SD + Wake word | ⏳ |
| 7   | Tauri masaüstü uygulaması | ⏳ |
| 8   | React Native mobil (opsiyonel) | ⏳ |
| 9   | Sertleştirme + dokümantasyon + demo | ⏳ |
