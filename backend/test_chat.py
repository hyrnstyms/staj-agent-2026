"""
test_chat.py
------------
Etkileşimli terminal istemcisi — asistan backend'ini doğrudan test etmek için.

Kullanım:
    cd backend
    venv\\Scripts\\python test_chat.py

Özellikler:
    - Kalıcı oturum ID (konuşma bağlamı korunur)
    - Onay bekleme durumunu gösterir
    - /approve <id> ve /reject <id> komutları ile onay verilebilir
    - /clear ile oturum sıfırlanır
    - /status ile backend sağlık durumu gösterilir
    - /help ile komutlar listesi görülür
"""

import sys
import uuid
import requests

# ── Konfigürasyon ─────────────────────────────────────────────────────────────
BASE_URL = "http://localhost:8000"
API_KEY  = "dev-api-key-change-in-production"
HEADERS  = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

# Windows terminal encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Oturum ────────────────────────────────────────────────────────────────────
SESSION_ID = str(uuid.uuid4())


def print_banner():
    print("\n" + "=" * 60)
    print("🤖  YEREL AI ASISTAN — Etkileşimli Terminal")
    print(f"    Backend   : {BASE_URL}")
    print(f"    Oturum ID : {SESSION_ID[:8]}...")
    print("    Komutlar  : /help | /status | /clear | /approve <id> | /reject <id> | q")
    print("=" * 60 + "\n")


def show_help():
    print("""
Komutlar:
  /help               — Bu yardım mesajını göster
  /status             — Backend sağlık durumunu göster
  /clear              — Mevcut konuşmayı sıfırla (yeni oturum)
  /approve <id>       — Bekleyen işlemi onayla
  /reject <id>        — Bekleyen işlemi reddet
  /pending            — Bekleyen onay isteklerini listele
  q / exit / çıkış   — Programdan çık
""")


def check_status():
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        r.raise_for_status()
        d = r.json()
        print("\n✅ Backend çalışıyor")
        print(f"   Model         : {d.get('model')}")
        print(f"   Ollama URL    : {d.get('ollama_url')}")
        print(f"   Aktif oturum  : {d.get('active_sessions')}")
        print(f"   Bekleyen onay : {d.get('pending_approvals')}\n")
    except requests.exceptions.ConnectionError:
        print("\n❌ Backend'e ulaşılamadı. uvicorn başlatıldı mı?\n")
    except Exception as e:
        print(f"\n❌ Durum sorgulama hatası: {e}\n")


def list_pending():
    try:
        r = requests.get(f"{BASE_URL}/approvals/pending", headers=HEADERS, timeout=5)
        r.raise_for_status()
        d = r.json()
        if d["total"] == 0:
            print("\n📋 Bekleyen onay isteği yok.\n")
        else:
            print(f"\n📋 {d['total']} bekleyen onay isteği:")
            for item in d["items"]:
                print(f"   [{item['approval_id'][:8]}...] {item['tool_name']} — {item.get('description', '')}")
            print()
    except Exception as e:
        print(f"\n❌ Hata: {e}\n")


def approve_action(approval_id: str):
    try:
        r = requests.post(f"{BASE_URL}/approve/{approval_id}", headers=HEADERS, timeout=10)
        r.raise_for_status()
        d = r.json()
        print(f"\n✅ Onaylandı: {d.get('message')}\n")
    except Exception as e:
        print(f"\n❌ Onay hatası: {e}\n")


def reject_action(approval_id: str):
    try:
        r = requests.post(f"{BASE_URL}/reject/{approval_id}", headers=HEADERS, timeout=10)
        r.raise_for_status()
        d = r.json()
        print(f"\n🚫 Reddedildi: {d.get('message')}\n")
    except Exception as e:
        print(f"\n❌ Red hatası: {e}\n")


def send_message(message: str, approval_id: str | None = None) -> dict | None:
    payload = {
        "message": message,
        "session_id": SESSION_ID,
    }
    if approval_id:
        payload["approval_id"] = approval_id

    try:
        r = requests.post(f"{BASE_URL}/chat", json=payload, headers=HEADERS, timeout=120)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        print("\n❌ Backend'e ulaşılamadı. Önce uvicorn başlatın:\n")
        print("   cd backend && venv\\Scripts\\activate && uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 1\n")
        return None
    except requests.exceptions.Timeout:
        print("\n⏳ Zaman aşımı — model yanıt vermedi. Model yüklü mü?\n")
        return None
    except Exception as e:
        print(f"\n❌ HATA: {e}\n")
        return None


def main():
    global SESSION_ID

    print_banner()

    while True:
        try:
            user_input = input("👤 Siz: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nGörüşmek üzere! 👋\n")
            break

        if not user_input:
            continue

        # ── Özel komutlar ──────────────────────────────────────────────────────
        if user_input.lower() in ("q", "exit", "çıkış", "quit"):
            print("\nGörüşmek üzere! 👋\n")
            break

        if user_input == "/help":
            show_help()
            continue

        if user_input == "/status":
            check_status()
            continue

        if user_input == "/clear":
            SESSION_ID = str(uuid.uuid4())
            print(f"\n🔄 Yeni oturum: {SESSION_ID[:8]}...\n")
            continue

        if user_input == "/pending":
            list_pending()
            continue

        if user_input.startswith("/approve "):
            parts = user_input.split(" ", 1)
            if len(parts) == 2:
                approve_action(parts[1].strip())
            else:
                print("Kullanım: /approve <approval_id>\n")
            continue

        if user_input.startswith("/reject "):
            parts = user_input.split(" ", 1)
            if len(parts) == 2:
                reject_action(parts[1].strip())
            else:
                print("Kullanım: /reject <approval_id>\n")
            continue

        # ── Normal mesaj ──────────────────────────────────────────────────────
        data = send_message(user_input)
        if data is None:
            continue

        message     = data.get("message", "")
        status      = data.get("status", "")
        tool_name   = data.get("tool_name")
        approval_id = data.get("approval_id")
        category    = data.get("category")

        print(f"\n🤖 Asistan: {message}\n")

        if tool_name:
            print(f"   🔧 Tool     : {tool_name}")
        if category:
            print(f"   📂 Kategori : {category}")

        if status == "pending_approval" and approval_id:
            print(f"\n   ⚠️  ONAY GEREKİYOR  (ID: {approval_id[:8]}...)")
            print(f"   → Onaylamak için: /approve {approval_id}")
            print(f"   → Reddetmek için: /reject  {approval_id}")

        print("-" * 60)


if __name__ == "__main__":
    main()
