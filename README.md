# Asistan — Yerel AI Asistanı

> **Staj Bitirme Projesi** · Faz 0–6 tamamlandı (Faz 7–9 planlandı)

Yerel (self-hosted) çalışan, Ollama üzerinde Qwen2.5 modeli kullanan,
dosya sistemi / veritabanı / HR / kod & git / mail & takvim / uygulama kontrolü / multimodal
erişimli, onay mekanizmalı ve tam loglu bir **tool-calling AI asistanı**.

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
# - GITHUB_TOKEN: GitHub PR işlemleri için (opsiyonel)
# - N8N_WEBHOOK_URL: Mail/Takvim için n8n webhook URL'i
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

## Etkileşimli Terminal İstemcisi

```bash
cd local-agent/backend
venv\Scripts\activate  # Windows
python test_chat.py
```

**Komutlar:**

| Komut | Açıklama |
|-------|----------|
| `/status` | Backend sağlık durumunu göster |
| `/pending` | Bekleyen onay isteklerini listele |
| `/approve <id>` | Bekleyen işlemi onayla |
| `/reject <id>` | Bekleyen işlemi reddet |
| `/clear` | Konuşmayı sıfırla (yeni oturum) |
| `/help` | Tüm komutları listele |
| `q` / `exit` | Programdan çık |

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

# Yanıt: {"status": "pending_approval", "approval_id": "uuid-here", ...}

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
  -d '{"message": "Ahmet Yılmaz'\''ın izin bakiyesi nedir?", "session_id": "demo-hr"}'
```

### Güvenli Kod Çalıştırma — Docker Sandbox (Faz 3)

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key-change-in-production" \
  -d '{"message": "sandbox/test.py dosyasını çalıştır", "session_id": "demo-code"}'
```

### Uygulama Kontrolü (Faz 5)

```bash
# Notepad'i aç
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key-change-in-production" \
  -d '{"message": "notepad aç", "session_id": "demo-app"}'

# Çalışan uygulamaları listele
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key-change-in-production" \
  -d '{"message": "hangi uygulamalar çalışıyor?", "session_id": "demo-app"}'
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
pytest tests/ -v

# Doğruluk testi (Ollama ile)
pytest tests/test_tool_calling_accuracy.py -v -s

# Coverage raporu
pytest tests/ --cov=. --cov-report=term-missing
```

---

## ⚠️ Kritik Uyarılar

### Faz 1 Geçici Auth
Tüm API istekleri `X-API-Key` header'ı ile doğrulanır.
**Bu geçici bir mekanizmadır — production'da JWT tabanlı auth kullanılmalıdır.**

### Tek Worker Zorunlu
`pending_approvals` ve `ConversationMemory` in-memory tutulduğu için
uvicorn **`--workers 1`** ile çalıştırılmalıdır.

### Sandbox Güvenliği
Dosya işlemleri yalnızca `SANDBOX_ROOT` dizini altında çalışır.
`../../etc/passwd` gibi path traversal girişimleri reddedilir.

### Uygulama Güvenliği
Uygulama açma/kapatma yalnızca `ALLOWED_APPS` whitelist'indeki uygulamalara izin verir.
Shell injection koruması için `shell=False` kullanılır.

---

## Proje Yapısı

```
local-agent/
├── backend/
│   ├── core/           # Agent, Router, Executor, Approval, Memory, Permissions, Logger
│   ├── mcp_servers/    # Filesystem, DB, HR, Code/Git, Mail/Calendar, App (tam implemente)
│   ├── multimodal/     # STT (Whisper), TTS (pyttsx3), Vision (Ollama), Image Gen (SD)
│   ├── db/             # SQLAlchemy modelleri, seed verisi (upsert destekli)
│   ├── api/            # FastAPI app + WebSocket + onay endpoint'leri
│   └── tests/          # 137 test, 13 skipped (LLM testleri)
├── docker-compose.yml   # Ollama + Backend
└── docs/               # Mimari, tool listesi, kurulum, güvenlik
```

---

## Geliştirme Fazları

| Faz | Kapsam | Durum |
|-----|--------|-------|
| 0   | Temel altyapı, config, DB | ✅ Tamamlandı |
| 1   | Agent core, router, onay, RBAC, loglama, filesystem | ✅ Tamamlandı |
| 2   | DB server (tam) + HR senaryosu (RBAC, Parametreli Sorgu) | ✅ Tamamlandı |
| 3   | Docker sandbox + Kod/Git (Command Injection Koruması) | ✅ Tamamlandı |
| 4   | Mail + Takvim (n8n webhook entegrasyonu) | ✅ Tamamlandı |
| 5   | Uygulama kontrolü (Windows ALLOWED_APPS whitelist) | ✅ Tamamlandı |
| 6   | Whisper STT + pyttsx3 TTS + Ollama Vision + SD image gen | ✅ Tamamlandı |
| 7   | Tauri masaüstü uygulaması | ⏳ Planlandı |
| 8   | React Native mobil (opsiyonel) | ⏳ |
| 9   | Sertleştirme + dokümantasyon + demo | ⏳ |

---

## Desteklenen Tool'lar

| Kategori | Tool'lar |
|----------|---------|
| **dosya** | `file_read`, `file_write`, `file_delete`, `file_list`, `file_move` |
| **veritabani** | `db_list_tables`, `db_get_schema`, `db_query`, `db_insert`, `db_update`, `db_delete` |
| **hr_personel** | `get_employee_leave_balance`, `get_employees_on_leave`, `request_leave`, `approve_leave` |
| **kod_git** | `code_run`, `code_lint`, `git_status`, `git_diff_preview`, `git_create_branch`, `git_commit_and_push`, `github_create_pull_request` |
| **mail_takvim** | `mail_read_inbox`, `mail_send`, `mail_extract_meeting`, `calendar_list_events`, `calendar_add_event`, `calendar_delete_event` |
| **uygulama** | `app_open`, `app_close`, `app_list_running` |
| **gorsel_ses** | `stt_transcribe`, `tts_speak`, `vision_describe`, `image_generate` |
