# Asistan — Mimari Dokümantasyon

## Genel Bakış

Asistan, **yerel (self-hosted) çalışan, Claude Desktop benzeri bir kişisel/kurumsal AI asistanı**dır. Kullanıcının izin verdiği kaynaklara (dosya sistemi, veritabanı, mail, takvim, GitHub, uygulamalar) erişip işlem yapabilen; metin, ses ve görsel girdi/çıktı destekleyen; onay mekanizmalı ve loglu bir **tool-calling agent** sistemidir.

## Mimari Diyagram

```
                     ┌──────────────────────────────┐
   Kullanıcı ───────▶│  Arayüz Katmanı                │
  (metin/ses/görsel)  │  - Masaüstü uygulaması (Tauri) │
                     │  - Web chat arayüzü (dev/test) │
                     └───────────────┬───────────────┘
                                     ▼
                     ┌──────────────────────────────┐
                     │  Giriş Ön-İşleme Katmanı        │
                     │  - STT (Whisper) → ses → metin  │
                     │  - Vision → görsel → açıklama   │
                     └───────────────┬───────────────┘
                                     ▼
                     ┌──────────────────────────────┐
                     │  AGENT CORE (FastAPI backend)  │
                     │  - Ollama + Qwen2.5:3b-instruct│
                     │  - 2 Aşamalı Kategori Router    │
                     │  - Tool-calling loop            │
                     │  - Onay mekanizması             │
                     │  - RBAC yetkilendirme            │
                     │  - Loglama                       │
                     └───────────────┬───────────────┘
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                       ▼
   ┌─────────────────┐  ┌──────────────────┐    ┌──────────────────┐
   │ MCP Server'lar     │  │ n8n Webhook'ları    │    │ Multimodal         │
   │ - filesystem       │  │ - Gmail OAuth       │    │ - Whisper (STT)    │
   │ - database         │  │ - Google Calendar   │    │ - pyttsx3 (TTS)    │
   │ - code_git         │  │                      │    │ - qwen2-vl (Vision)│
   │ - app              │  │                      │    │ - SD (Image Gen)   │
   │ - hr               │  │                      │    │                    │
   └─────────────────┘  └──────────────────┘    └──────────────────┘
```

## 2 Aşamalı Kategori Router

3B model aynı anda çok fazla tool gördüğünde yanlış seçim yapar. Bu yüzden **iki aşamalı** akış kullanılır:

### Aşama 1 — Kategori Seçimi
Modele sadece 7 kategori gösterilir (tool tanımı değil):
```
["dosya", "veritabani", "kod_git", "mail_takvim", "uygulama", "gorsel_ses", "genel_sohbet"]
```

### Aşama 2 — Tool Seçimi
Seçilen kategorideki 4-8 tool modele tanıtılır, model bunlardan birini ve parametrelerini seçer.

### Aşama 3 — Onay Kontrolü
Riskli tool seçildiyse kullanıcı onayı istenir.

### Aşama 4 — Yürütme + Loglama
Tool çalıştırılır, sonuç DB log tablosuna yazılır.

## MCP (Model Context Protocol)

Her tool grubu standart MCP interface'i sağlar:
- `list_tools()` → Tool şemalarını döner
- `call_tool(name, arguments)` → Tool'u çalıştırır

HTTP endpoint'leri:
- `GET /mcp/servers` — Kayıtlı server listesi
- `GET /mcp/tools` — Tüm tool şemaları
- `POST /mcp/call` — Tool çalıştırma

## Teknoloji Yığını

| Katman | Teknoloji |
|---|---|
| LLM | Ollama + Qwen2.5:3b-instruct |
| Backend | Python 3.11+ / FastAPI |
| Frontend | React + TypeScript + Tauri |
| DB | SQLite (→ PostgreSQL) |
| ORM | SQLAlchemy |
| Otomasyon | n8n (Docker) |
| Sandbox | Docker container |
| State | Zustand (frontend) |

## Modül Haritası

```
backend/
├── core/           → Agent loop, router, executor, onay, izin, hafıza, log
├── mcp_servers/    → Tool implementasyonları (filesystem, db, hr, code, mail, app)
├── integrations/   → n8n client, mail/calendar/github wrapper'lar
├── multimodal/     → STT, TTS, Vision, Image Gen, Wake Word
├── api/            → FastAPI (REST + WebSocket + MCP endpoint'ler)
├── db/             → SQLAlchemy modelleri ve veritabanı yönetimi
└── tests/          → Unit ve entegrasyon testleri

desktop-app/
├── src/            → React bileşenleri (Chat, Input, Approval, Settings)
├── src-tauri/      → Rust backend (Tauri)
└── public/         → Statik dosyalar
```
