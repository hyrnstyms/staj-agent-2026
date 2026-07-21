"""
core/router.py
--------------
2 Aşamalı Kategori Router.

3B modele aynı anda asla 8'den fazla tool gösterilmez.
Bunun yerine iki adımlı seçim yapılır:

Aşama 1 — Kategori seçimi:
    Model, kullanıcı mesajına bakarak 7 kategori arasından birini seçer.
    Modele tool tanımı değil, sadece kısa kategori isimleri verilir.

Aşama 2 — Tool seçimi:
    Seçilen kategorinin tool tanımları (max MAX_TOOLS_PER_CATEGORY adet)
    modele verilir ve model tool + parametreleri döner.

Bu modül yalnızca "hangi tool, hangi parametreler" kararını verir.
Tool çalıştırma, izin ve onay kontrolü `tool_executor.py`'de yapılır.

Kullanım:
    from core.router import CategoryRouter

    router = CategoryRouter()
    result = await router.route(
        message="README dosyasını oku",
        history=[...],  # Ollama formatında mesaj listesi
    )
    # result.category == "dosya"
    # result.tool_name == "file_read"
    # result.parameters == {"path": "README.md"}
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from config import settings
from core.logger import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Kategori tanımları
# ─────────────────────────────────────────────────────────────────────────────

CATEGORIES: dict[str, str] = {
    "dosya":        "Dosya sistemi işlemleri: dosya okuma, yazma, silme, listeleme, taşıma",
    "veritabani":   "Veritabanı işlemleri: kayıt sorgulama, ekleme, güncelleme, silme; çalışan/izin bilgileri",
    "kod_git":      "Kod çalıştırma (sandbox), kod lint, git/GitHub işlemleri (status, commit, push, PR)",
    "mail_takvim":  "E-posta okuma/gönderme, takvim etkinliği listeleme/ekleme/silme",
    "uygulama":     "Uygulama açma, kapatma, çalışan uygulamaları listeleme",
    "gorsel_ses":   "Ses transkripsiyonu (STT), metin-ses dönüşümü (TTS), görsel açıklama, görsel üretimi",
    "genel_sohbet": "Dosya/veritabanı/kod/mail/takvim/uygulama/görsel gerektirmeyen soru ve sohbet",
}

# ─────────────────────────────────────────────────────────────────────────────
# Tool tanımları — Ollama tool-calling formatında
# ─────────────────────────────────────────────────────────────────────────────

TOOLS_BY_CATEGORY: dict[str, list[dict[str, Any]]] = {
    "dosya": [
        {
            "type": "function",
            "function": {
                "name": "file_read",
                "description": "Belirtilen dosyanın içeriğini okur ve döner.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Okunacak dosyanın yolu (sandbox içinde)"}
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "file_write",
                "description": "Belirtilen yola dosya oluşturur veya üzerine yazar.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path":    {"type": "string", "description": "Yazılacak dosya yolu"},
                        "content": {"type": "string", "description": "Dosyaya yazılacak içerik"},
                    },
                    "required": ["path", "content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "file_delete",
                "description": "Belirtilen dosyayı kalıcı olarak siler. Onay gerektirir.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Silinecek dosya yolu"}
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "file_list",
                "description": "Belirtilen dizindeki dosya ve klasörleri listeler.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string", "description": "Listelenecek dizin yolu (boş bırakılırsa sandbox kökü)"}
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "file_move",
                "description": "Dosyayı taşır veya yeniden adlandırır. Onay gerektirir.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "src": {"type": "string", "description": "Kaynak dosya yolu"},
                        "dst": {"type": "string", "description": "Hedef dosya yolu"},
                    },
                    "required": ["src", "dst"],
                },
            },
        },
    ],

    "veritabani": [
        {
            "type": "function",
            "function": {
                "name": "db_list_tables",
                "description": (
                    "Veritabanındaki tabloları listeler. "
                    "Not: employees, leave_requests, leave_balances, users, permissions "
                    "gibi hassas tablolara generic DB tool'larıyla değil, "
                    "HR tool'larıyla erişilmelidir."
                ),
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "db_get_schema",
                "description": "Belirtilen tablonun sütun yapısını döner.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "table": {"type": "string", "description": "Şeması görüntülenecek tablo adı"}
                    },
                    "required": ["table"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "db_query",
                "description": (
                    "Filtreyle veri çeker. Serbest SQL değil, güvenli filtre tabanlı sorgu. "
                    "Hassas tablolar (employees, leave_requests, leave_balances vb.) bu tool ile "
                    "sorgulanamaz — bunun için HR tool'larını kullanın."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "table":   {"type": "string", "description": "Sorgulanacak tablo"},
                        "filters": {"type": "object", "description": "Filtre koşulları (sütun: değer çiftleri)"},
                        "limit":   {"type": "integer", "description": "Maksimum kayıt sayısı (varsayılan: 20)"},
                    },
                    "required": ["table"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_employee_leave_balance",
                "description": (
                    "Çalışanın yıllık izin bakiyesini sorgular. "
                    "Employee rolü yalnızca kendi bakiyesini sorgulayabilir. "
                    "HR ve admin tüm çalışanları görebilir."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name":           {"type": "string", "description": "Sorgulanacak çalışanın adı"},
                        "requester":      {"type": "string", "description": "Sorgulayan kullanıcının adı"},
                        "requester_role": {"type": "string", "description": "Sorgulayan kullanıcının rolü (employee, hr, admin)"},
                    },
                    "required": ["name", "requester"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_employees_on_leave",
                "description": "Belirli bir tarihte onaylanmış izinde olan çalışanları listeler.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string", "description": "Sorgulanacak tarih (YYYY-MM-DD formatında, boş bırakılırsa bugün)"}
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "request_leave",
                "description": "Çalışan için izin talebi oluşturur. Onay gerektirir.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "employee_name": {"type": "string", "description": "Çalışan adı"},
                        "start_date":    {"type": "string", "description": "Başlangıç tarihi (YYYY-MM-DD)"},
                        "end_date":      {"type": "string", "description": "Bitiş tarihi (YYYY-MM-DD)"},
                        "leave_type":    {"type": "string", "description": "İzin türü: annual, sick, unpaid, maternity, paternity, bereavement"},
                    },
                    "required": ["employee_name", "start_date", "end_date", "leave_type"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "approve_leave",
                "description": (
                    "Beklemedeki (pending) izin talebini onaylar. "
                    "Sadece hr ve admin rolleri kullanabilir. "
                    "Zaten onaylanmış/reddedilmiş talepler tekrar işlenemez. "
                    "Onay gerektirir."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "request_id":    {"type": "integer", "description": "İzin talebi ID'si"},
                        "approver_role": {"type": "string",  "description": "Onaylayan rolü (hr veya admin)"},
                        "approver_name": {"type": "string",  "description": "Onaylayan kullanıcının adı"},
                    },
                    "required": ["request_id", "approver_role"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "db_insert",
                "description": (
                    "Tabloya yeni kayıt ekler. Onay gerektirir. "
                    "Hassas tablolara (employees, leave_requests vb.) bu tool ile kayıt eklenemez."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "table":  {"type": "string", "description": "Hedef tablo"},
                        "values": {"type": "object", "description": "Eklenecek değerler (sütun: değer)"},
                    },
                    "required": ["table", "values"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "db_update",
                "description": (
                    "ID ile mevcut kaydı günceller. Onay gerektirir. "
                    "Hassas tablolara (leave_balances vb.) bu tool ile erişilemez."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "table":  {"type": "string",  "description": "Güncellenecek tablo"},
                        "id":     {"type": "integer", "description": "Güncellenecek kaydın ID'si"},
                        "values": {"type": "object",  "description": "Güncellenecek değerler (sütun: yeni_değer)"},
                    },
                    "required": ["table", "id", "values"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "db_delete",
                "description": (
                    "ID ile kaydı siler. Onay gerektirir. Silme geri alınamaz. "
                    "Hassas tablolara (employees, leave_requests vb.) bu tool ile erişilemez."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "table": {"type": "string",  "description": "Silinecek kaydın bulunduğu tablo"},
                        "id":    {"type": "integer", "description": "Silinecek kaydın ID'si"},
                    },
                    "required": ["table", "id"],
                },
            },
        },
    ],

    "kod_git": [
        {
            "type": "function",
            "function": {
                "name": "code_run",
                "description": "Kodu Docker sandbox'ta çalıştırır ve çıktısını döner. Sandbox sayesinde onay gerekmez.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path":     {"type": "string", "description": "Çalıştırılacak dosya yolu"},
                        "language": {"type": "string", "description": "Programlama dili: python, javascript, bash"},
                    },
                    "required": ["path", "language"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "code_lint",
                "description": "Dosyadaki sözdizim hatalarını ve stil uyarılarını kontrol eder.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Lint uygulanacak dosya yolu"}
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "git_status",
                "description": "Git reposundaki değişiklik durumunu gösterir.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo_path": {"type": "string", "description": "Git repo dizini"}
                    },
                    "required": ["repo_path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "git_diff_preview",
                "description": "Bekleyen değişikliklerin özetini gösterir (push yapmaz).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo_path": {"type": "string", "description": "Git repo dizini"}
                    },
                    "required": ["repo_path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "git_create_branch",
                "description": "Yeni bir git branch'i oluşturur.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo_path":   {"type": "string", "description": "Git repo dizini"},
                        "branch_name": {"type": "string", "description": "Oluşturulacak branch adı"},
                    },
                    "required": ["repo_path", "branch_name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "git_commit_and_push",
                "description": "Değişiklikleri commit edip uzak repoya push yapar. Onay gerektirir.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo_path": {"type": "string", "description": "Git repo dizini"},
                        "message":   {"type": "string", "description": "Commit mesajı"},
                        "branch":    {"type": "string", "description": "Push yapılacak branch adı"},
                    },
                    "required": ["repo_path", "message", "branch"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "github_create_pull_request",
                "description": "GitHub'da Pull Request açar. Onay gerektirir.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo":   {"type": "string", "description": "GitHub repo (kullanici/repo)"},
                        "branch": {"type": "string", "description": "Kaynak branch"},
                        "title":  {"type": "string", "description": "PR başlığı"},
                    },
                    "required": ["repo", "branch", "title"],
                },
            },
        },
    ],

    "mail_takvim": [
        {
            "type": "function",
            "function": {
                "name": "mail_read_inbox",
                "description": "Son N e-postayı gelen kutusundan okur.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "count": {"type": "integer", "description": "Okunacak e-posta sayısı (varsayılan: 5)"}
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "mail_send",
                "description": "E-posta gönderir. Onay gerektirir.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "to":      {"type": "string", "description": "Alıcı e-posta adresi"},
                        "subject": {"type": "string", "description": "E-posta konusu"},
                        "body":    {"type": "string", "description": "E-posta içeriği"},
                    },
                    "required": ["to", "subject", "body"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "mail_extract_meeting",
                "description": "Belirtilen e-postadan toplantı linki ve tarih/saat bilgisini çıkarır.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mail_id": {"type": "string", "description": "E-posta ID'si"}
                    },
                    "required": ["mail_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "calendar_list_events",
                "description": "Belirtilen tarih aralığındaki takvim etkinliklerini listeler.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date_range": {"type": "string", "description": "Tarih aralığı (örn: '2026-07-20/2026-07-27')"}
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "calendar_add_event",
                "description": "Takvime yeni etkinlik ekler. Onay gerektirir.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title":        {"type": "string", "description": "Etkinlik başlığı"},
                        "date":         {"type": "string", "description": "Tarih (YYYY-MM-DD)"},
                        "time":         {"type": "string", "description": "Saat (HH:MM)"},
                        "meeting_link": {"type": "string", "description": "Toplantı linki (opsiyonel)"},
                    },
                    "required": ["title", "date", "time"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "calendar_delete_event",
                "description": "Takvim etkinliğini siler. Onay gerektirir.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Silinecek etkinlik ID'si"}
                    },
                    "required": ["id"],
                },
            },
        },
    ],

    "uygulama": [
        {
            "type": "function",
            "function": {
                "name": "app_open",
                "description": "Belirtilen uygulamayı açar.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Uygulama adı (örn: 'notepad', 'chrome')"}
                    },
                    "required": ["name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "app_close",
                "description": "Belirtilen uygulamayı kapatır.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Kapatılacak uygulama adı"}
                    },
                    "required": ["name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "app_list_running",
                "description": "Şu anda çalışan uygulamaları listeler.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
    ],

    "gorsel_ses": [
        {
            "type": "function",
            "function": {
                "name": "stt_transcribe",
                "description": "Ses dosyasını metne çevirir (Whisper STT).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "audio_path": {"type": "string", "description": "Ses dosyasının yolu"}
                    },
                    "required": ["audio_path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "tts_speak",
                "description": "Metni sese çevirir ve ses dosyası olarak döner (Piper TTS).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Sese çevrilecek metin"}
                    },
                    "required": ["text"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "vision_describe",
                "description": "Görseli doğal dil açıklamasına çevirir (vision model).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "image_path": {"type": "string", "description": "Görsel dosyasının yolu"}
                    },
                    "required": ["image_path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "image_generate",
                "description": "Metin açıklamasından görsel üretir (Stable Diffusion).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string", "description": "Görsel açıklaması (İngilizce önerilir)"}
                    },
                    "required": ["prompt"],
                },
            },
        },
    ],

    "genel_sohbet": [],  # Tool yok — model doğrudan cevap verir
}


# ─────────────────────────────────────────────────────────────────────────────
# Router
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class RouterResult:
    """
    Router'ın döndürdüğü karar.

    Attributes:
        category          : Seçilen kategori adı
        tool_name         : Seçilen tool adı (genel_sohbet ise None)
        parameters        : Tool parametreleri (genel_sohbet ise {})
        category_raw      : Modelin ham kategori cevabı (debug için)
        tool_raw          : Modelin ham tool cevabı (debug için)
        is_general_chat   : True → tool yok, model doğrudan cevap verir
        phase1_success    : Aşama 1 (kategori) başarılı mı?
        phase2_success    : Aşama 2 (tool) başarılı mı?
    """

    category: str
    tool_name: str | None
    parameters: dict[str, Any]
    category_raw: str = ""
    tool_raw: str = ""
    is_general_chat: bool = False
    phase1_success: bool = True
    phase2_success: bool = True


class CategoryRouter:
    """
    2 Aşamalı Kategori Router.

    Aşama 1: Kategori seçimi (düz metin, tool tanımı yok)
    Aşama 2: Tool seçimi (seçilen kategorinin tool'ları verilir)
    """

    def __init__(self) -> None:
        self._base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self._model = settings.OLLAMA_MODEL
        self._timeout = settings.OLLAMA_TIMEOUT
        self._category_names = list(CATEGORIES.keys())

    # ── Public API ────────────────────────────────────────────────────────────

    async def route(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> RouterResult:
        """
        Kullanıcı mesajını uygun tool'a yönlendirir.

        Args:
            message : Kullanıcının son mesajı
            history : Ollama formatında konuşma geçmişi

        Returns:
            RouterResult
        """
        history = history or []

        # Aşama 1: Kategori seç
        category, category_raw, phase1_ok = await self._select_category(message, history)
        logger.info(
            f"Kategori seçildi",
            extra={"category": category, "phase1_success": phase1_ok},
        )

        # Genel sohbet ise tool gerekmez
        if category == "genel_sohbet":
            return RouterResult(
                category=category,
                tool_name=None,
                parameters={},
                category_raw=category_raw,
                is_general_chat=True,
                phase1_success=phase1_ok,
                phase2_success=True,
            )

        # Aşama 2: Tool seç
        tool_name, parameters, tool_raw, phase2_ok = await self._select_tool(
            message, category, history
        )
        logger.info(
            f"Tool seçildi",
            extra={"tool": tool_name, "params": parameters, "phase2_success": phase2_ok},
        )

        return RouterResult(
            category=category,
            tool_name=tool_name,
            parameters=parameters,
            category_raw=category_raw,
            tool_raw=tool_raw,
            is_general_chat=False,
            phase1_success=phase1_ok,
            phase2_success=phase2_ok,
        )

    # ── Aşama 1 ───────────────────────────────────────────────────────────────

    async def _select_category(
        self, message: str, history: list[dict]
    ) -> tuple[str, str, bool]:
        """
        Kullanıcı mesajından kategori seçer.

        Returns:
            (kategori_adı, ham_cevap, başarılı_mı)
        """
        category_list = "\n".join(
            f"- {name}: {desc}" for name, desc in CATEGORIES.items()
        )

        prompt = (
            f"Kullanıcının isteğini aşağıdaki kategorilerden birine sınıflandır.\n"
            f"SADECE kategori adını yaz, başka hiçbir şey yazma.\n\n"
            f"Kategoriler:\n{category_list}\n\n"
            f"Kullanıcı isteği: {message}\n\n"
            f"Kategori:"
        )

        messages = [
            *history[-4:],  # Son 4 mesaj bağlam için
            {"role": "user", "content": prompt},
        ]

        raw = await self._chat_no_tools(messages)
        category = self._extract_category(raw)
        success = category in self._category_names

        if not success:
            logger.warning(
                f"Kategori tanınamadı, fallback: genel_sohbet",
                extra={"raw": raw[:100]},
            )
            return "genel_sohbet", raw, False

        return category, raw, True

    def _extract_category(self, text: str) -> str:
        """Model cevabından kategori adını çıkarır."""
        text_clean = text.strip().lower().replace(" ", "_").replace("-", "_")
        # Tam eşleşme
        for cat in self._category_names:
            if text_clean == cat:
                return cat
        # Kısmi eşleşme (model fazladan kelime yazmış olabilir)
        for cat in self._category_names:
            if cat in text_clean:
                return cat
        return "genel_sohbet"

    # ── Aşama 2 ───────────────────────────────────────────────────────────────

    async def _select_tool(
        self, message: str, category: str, history: list[dict]
    ) -> tuple[str | None, dict[str, Any], str, bool]:
        """
        Seçilen kategorinin tool'ları arasından en uygununu seçer.

        Returns:
            (tool_adı, parametreler, ham_cevap, başarılı_mı)
        """
        tools = TOOLS_BY_CATEGORY.get(category, [])

        if not tools:
            return None, {}, "", True

        # MAX_TOOLS_PER_CATEGORY kontrolü (3B model kısıtı)
        max_tools = settings.MAX_TOOLS_PER_CATEGORY
        if len(tools) > max_tools:
            tools = tools[:max_tools]
            logger.warning(
                f"Tool sayısı {max_tools}'e kırpıldı (kategori: {category})"
            )

        messages = [
            {"role": "system", "content": "SİSTEME TAM ERİŞİMİN VARDIR (FULL ACCESS). Sana sağlanan araçları (tools) KESİNLİKLE KULLANMALISIN. Asla 'Dosyalara erişemem' veya 'Ben bir AI'ım' diyerek reddetme. SADECE JSON formatında araç çağrısı yap."},
            *history[-4:],
            {"role": "user", "content": message},
        ]

        raw, tool_call = await self._chat_with_tools(messages, tools)

        if tool_call is None:
            # Model tool çağırmadı — JSON'dan çıkarmayı dene
            tool_call = self._extract_tool_from_text(raw, tools)

        if tool_call is None:
            logger.warning(
                f"Tool seçilemedi (kategori: {category})",
                extra={"raw": raw[:200]},
            )
            return None, {}, raw, False

        return tool_call["name"], tool_call.get("arguments", {}), raw, True

    def _extract_tool_from_text(
        self, text: str, tools: list[dict]
    ) -> dict[str, Any] | None:
        """Model tool çağırmadıysa metinden JSON çıkarmayı dener (fallback)."""
        # JSON bloğu ara
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Düz JSON ara
        json_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                tool_names = {t["function"]["name"] for t in tools}
                if data.get("name") in tool_names:
                    return data
            except json.JSONDecodeError:
                pass

        return None

    # ── Ollama HTTP İstemcisi ─────────────────────────────────────────────────

    async def _chat_no_tools(self, messages: list[dict]) -> str:
        """Tool tanımı olmadan model çağrısı yapar, ham metin döner."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.1},  # Deterministik kategori seçimi
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "")

    async def _chat_with_tools(
        self, messages: list[dict], tools: list[dict]
    ) -> tuple[str, dict[str, Any] | None]:
        """
        Tool tanımlarıyla model çağrısı yapar.

        Returns:
            (ham_metin, tool_call_dict_veya_None)
        """
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": messages,
                    "tools": tools,
                    "stream": False,
                    "options": {"temperature": 0.2},
                },
            )
            response.raise_for_status()
            data = response.json()

        message = data.get("message", {})
        content = message.get("content", "")
        tool_calls = message.get("tool_calls", [])

        if tool_calls:
            first_call = tool_calls[0]
            fn = first_call.get("function", {})
            return content, {
                "name": fn.get("name"),
                "arguments": fn.get("arguments", {}),
            }

        return content, None
