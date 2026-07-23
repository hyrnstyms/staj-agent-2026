"""
tests/test_tool_calling_accuracy.py
------------------------------------
Kategori Router ve Tool Seçim Doğruluk Testi.

Bu test gerçek Ollama bağlantısı gerektirir.
Ollama çalışmıyorsa testler otomatik olarak atlanır (pytest.skip).

Rapor formatı:
    Aşama 1 (Kategori Seçimi) başarı oranı: X/N (%YY)
    Aşama 2 (Tool Seçimi)     başarı oranı: X/N (%YY)
    Toplam Doğruluk            : X/N (%YY)

Hedef:
    Her iki aşama için minimum %70 başarı oranı.

Çalıştırmak için:
    cd backend
    pytest tests/test_tool_calling_accuracy.py -v -s

    # Ollama olmadan (mock):
    MOCK_ROUTER=1 pytest tests/test_tool_calling_accuracy.py -v
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ─────────────────────────────────────────────────────────────────────────────
# Test veri seti
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RouterTestCase:
    """Tek bir router test durumu."""
    input_message: str
    expected_category: str
    expected_tool: str | None
    description: str


TEST_CASES: list[RouterTestCase] = [
    # ── Dosya ────────────────────────────────────────────────────────────────
    RouterTestCase(
        input_message="README.md dosyasını oku",
        expected_category="dosya",
        expected_tool="file_read",
        description="Dosya okuma komutu",
    ),
    RouterTestCase(
        input_message="sandbox klasöründeki dosyaları listele",
        expected_category="dosya",
        expected_tool="file_list",
        description="Dosya listeleme",
    ),
    RouterTestCase(
        input_message="notlar.txt dosyasını sil",
        expected_category="dosya",
        expected_tool="file_delete",
        description="Dosya silme",
    ),
    RouterTestCase(
        input_message="config.txt dosyasına şu içeriği yaz: test=true",
        expected_category="dosya",
        expected_tool="file_write",
        description="Dosya yazma",
    ),
    RouterTestCase(
        input_message="eski.txt dosyasını yeni.txt olarak taşı",
        expected_category="dosya",
        expected_tool="file_move",
        description="Dosya taşıma",
    ),

    # ── Veritabanı ────────────────────────────────────────────────────────────
    RouterTestCase(
        input_message="bugün izinli çalışanlar kimler?",
        expected_category="veritabani",
        expected_tool="get_employees_on_leave",
        description="İzinli çalışanlar sorgusu",
    ),
    RouterTestCase(
        input_message="Ahmet'in izin bakiyesi ne kadar?",
        expected_category="veritabani",
        expected_tool="get_employee_leave_balance",
        description="İzin bakiyesi sorgusu",
    ),
    RouterTestCase(
        input_message="Zeynep için 1-5 Ağustos arası yıllık izin talebi oluştur",
        expected_category="veritabani",
        expected_tool="request_leave",
        description="İzin talebi oluşturma",
    ),
    RouterTestCase(
        input_message="veritabanındaki tabloları listele",
        expected_category="veritabani",
        expected_tool="db_list_tables",
        description="Tablo listeleme",
    ),

    # ── Kod/Git ───────────────────────────────────────────────────────────────
    RouterTestCase(
        input_message="hello.py dosyasını çalıştır",
        expected_category="kod_git",
        expected_tool="code_run",
        description="Kod çalıştırma",
    ),
    RouterTestCase(
        input_message="git reposunun durumunu göster",
        expected_category="kod_git",
        expected_tool="git_status",
        description="Git status",
    ),
    RouterTestCase(
        input_message="değişiklikleri 'fix: bug düzeltildi' mesajıyla commit et ve push yap",
        expected_category="kod_git",
        expected_tool="git_commit_and_push",
        description="Git commit ve push",
    ),

    # ── Mail/Takvim ───────────────────────────────────────────────────────────
    RouterTestCase(
        input_message="gelen kutuma bak, son 5 maili göster",
        expected_category="mail_takvim",
        expected_tool="mail_read_inbox",
        description="Mail okuma",
    ),
    RouterTestCase(
        input_message="yarınki takvim etkinliklerimi listele",
        expected_category="mail_takvim",
        expected_tool="calendar_list_events",
        description="Takvim listesi",
    ),

    # ── Uygulama ─────────────────────────────────────────────────────────────
    RouterTestCase(
        input_message="not defterini aç",
        expected_category="uygulama",
        expected_tool="app_open",
        description="Uygulama açma",
    ),
    RouterTestCase(
        input_message="şu an açık uygulamalar neler?",
        expected_category="uygulama",
        expected_tool="app_list_running",
        description="Açık uygulamalar",
    ),

    # ── Genel Sohbet ─────────────────────────────────────────────────────────
    RouterTestCase(
        input_message="merhaba, nasılsın?",
        expected_category="genel_sohbet",
        expected_tool=None,
        description="Genel selamlama",
    ),
    RouterTestCase(
        input_message="Python'da döngüler nasıl kullanılır?",
        expected_category="genel_sohbet",
        expected_tool=None,
        description="Genel soru",
    ),
]

CATEGORY_THRESHOLD = 0.70  # %70 minimum başarı
TOOL_THRESHOLD = 0.70


# ─────────────────────────────────────────────────────────────────────────────
# Ollama Bağlantı Kontrolü
# ─────────────────────────────────────────────────────────────────────────────

def is_ollama_available() -> bool:
    """Ollama sunucusunun erişilebilir olup olmadığını kontrol eder."""
    import httpx
    from config import settings
    try:
        resp = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Mock Router (MOCK_ROUTER=1 iken kullanılır)
# ─────────────────────────────────────────────────────────────────────────────

class MockRouterResult:
    """Test sırasında Ollama olmadan router simüle eder."""
    def __init__(self, tc: RouterTestCase):
        self.category = tc.expected_category
        self.tool_name = tc.expected_tool
        self.parameters = {}
        self.is_general_chat = tc.expected_category == "genel_sohbet"
        self.phase1_success = True
        self.phase2_success = True
        self.category_raw = tc.expected_category
        self.tool_raw = tc.expected_tool or ""


# ─────────────────────────────────────────────────────────────────────────────
# Testler
# ─────────────────────────────────────────────────────────────────────────────

USE_MOCK = os.environ.get("MOCK_ROUTER", "0") == "1"

if not USE_MOCK:
    pytestmark = pytest.mark.skipif(
        not is_ollama_available(),
        reason="Ollama erişilebilir değil. MOCK_ROUTER=1 ile mock kullanın.",
    )


@pytest.mark.asyncio
async def test_category_routing_accuracy():
    """
    Aşama 1: Kategori seçim doğruluk testi.
    Her test durumu için kategorinin doğru seçilip seçilmediğini ölçer.
    """
    from core.router import CategoryRouter

    router = CategoryRouter()

    phase1_results: list[tuple[RouterTestCase, bool]] = []

    for tc in TEST_CASES:
        if USE_MOCK:
            result = MockRouterResult(tc)
        else:
            result = await router.route(message=tc.input_message)

        correct = result.category == tc.expected_category
        phase1_results.append((tc, correct))

    # Rapor
    correct_count = sum(1 for _, ok in phase1_results if ok)
    total = len(phase1_results)
    accuracy = correct_count / total

    print(f"\n{'='*60}")
    print("AŞAMA 1 — KATEGORİ SEÇİMİ DOĞRULUK RAPORU")
    print(f"{'='*60}")
    for tc, ok in phase1_results:
        icon = "✅" if ok else "❌"
        print(f"  {icon} [{tc.expected_category}] {tc.description}")
        if not ok:
            from core.router import CategoryRouter
            if not USE_MOCK:
                r = await CategoryRouter().route(message=tc.input_message)
                print(f"     → Model seçti: {r.category!r} (beklenen: {tc.expected_category!r})")

    print(f"\n{'─'*60}")
    print(f"  Sonuç: {correct_count}/{total} doğru (%{accuracy*100:.1f})")
    print(f"  Hedef: minimum %{CATEGORY_THRESHOLD*100:.0f}")
    print(f"{'─'*60}\n")

    assert accuracy >= CATEGORY_THRESHOLD, (
        f"Kategori doğruluk oranı ({accuracy*100:.1f}%) "
        f"minimum hedefin ({CATEGORY_THRESHOLD*100:.0f}%) altında!"
    )


@pytest.mark.asyncio
async def test_tool_selection_accuracy():
    """
    Aşama 2: Tool seçim doğruluk testi.
    Sadece tool bekleyen (genel_sohbet olmayan) test durumlarını değerlendirir.
    """
    from core.router import CategoryRouter

    router = CategoryRouter()

    tool_cases = [tc for tc in TEST_CASES if tc.expected_tool is not None]
    phase2_results: list[tuple[RouterTestCase, bool]] = []

    for tc in tool_cases:
        if USE_MOCK:
            result = MockRouterResult(tc)
        else:
            result = await router.route(message=tc.input_message)

        correct = result.tool_name == tc.expected_tool
        phase2_results.append((tc, correct))

    # Rapor
    correct_count = sum(1 for _, ok in phase2_results if ok)
    total = len(phase2_results)
    accuracy = correct_count / total

    print(f"\n{'='*60}")
    print("AŞAMA 2 — TOOL SEÇİMİ DOĞRULUK RAPORU")
    print(f"{'='*60}")
    for tc, ok in phase2_results:
        icon = "✅" if ok else "❌"
        print(f"  {icon} [{tc.expected_tool}] {tc.description}")
        if not ok:
            from core.router import CategoryRouter
            if not USE_MOCK:
                r = await CategoryRouter().route(message=tc.input_message)
                print(f"     → Model seçti: {r.tool_name!r} (beklenen: {tc.expected_tool!r})")

    print(f"\n{'─'*60}")
    print(f"  Sonuç: {correct_count}/{total} doğru (%{accuracy*100:.1f})")
    print(f"  Hedef: minimum %{TOOL_THRESHOLD*100:.0f}")
    print(f"{'─'*60}\n")

    assert accuracy >= TOOL_THRESHOLD, (
        f"Tool doğruluk oranı ({accuracy*100:.1f}%) "
        f"minimum hedefin ({TOOL_THRESHOLD*100:.0f}%) altında!"
    )


@pytest.mark.asyncio
async def test_combined_accuracy_report():
    """
    Her iki aşamayı birleştirerek tam doğruluk raporu üretir.
    Bu test hiçbir zaman fail etmez — sadece rapor basar.
    """
    from core.router import CategoryRouter

    router = CategoryRouter()
    tool_cases = [tc for tc in TEST_CASES if tc.expected_tool is not None]

    cat_correct = 0
    tool_correct = 0

    print(f"\n{'='*70}")
    print(f"KAPSAMLI DOĞRULUK RAPORU — {len(TEST_CASES)} Test Durumu")
    print(f"{'='*70}")
    print(f"{'Açıklama':<35} {'Kat.Bek':<15} {'Tool Bek':<20} {'Kat.':<6} {'Tool'}")
    print(f"{'─'*70}")

    for tc in TEST_CASES:
        if USE_MOCK:
            result = MockRouterResult(tc)
        else:
            result = await router.route(message=tc.input_message)

        cat_ok = result.category == tc.expected_category
        tool_ok = (tc.expected_tool is None) or (result.tool_name == tc.expected_tool)

        if cat_ok:
            cat_correct += 1
        if tool_ok:
            tool_correct += 1

        cat_icon = "✅" if cat_ok else "❌"
        tool_icon = "✅" if tool_ok else "❌"

        print(
            f"{tc.description[:34]:<35} "
            f"{tc.expected_category:<15} "
            f"{(tc.expected_tool or 'N/A'):<20} "
            f"{cat_icon}      {tool_icon}"
        )

    cat_total = len(TEST_CASES)
    tool_total = len(tool_cases)

    print(f"\n{'─'*70}")
    print(f"Aşama 1 (Kategori): {cat_correct}/{cat_total} (%{cat_correct/cat_total*100:.1f})")
    print(f"Aşama 2 (Tool)    : {tool_correct}/{tool_total} (%{tool_correct/tool_total*100:.1f})")
    print(f"{'='*70}\n")

    # Bu test hiçbir zaman fail etmez — raporlama amaçlı
    assert True
