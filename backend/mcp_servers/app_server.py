"""
mcp_servers/app_server.py
--------------------------
Faz 5: Windows Uygulama Kontrol MCP Server.

Desteklenen İşlemler:
    - app_open(name)          : Belirtilen uygulamayı başlatır
    - app_close(name)         : Belirtilen uygulamayı kapatır
    - app_list_running()      : Çalışan uygulamaları listeler

Güvenlik:
    - Sadece ALLOWED_APPS whitelist'indeki uygulamalar açılabilir
    - shell=False (injection koruması)
    - Her işlem loglanır
"""

from __future__ import annotations

import subprocess
import sys
import webbrowser
from typing import Any

from core.logger import get_logger

logger = get_logger(__name__)

# Popüler websiteleri kısa isimden tam URL'e eşler
KNOWN_WEBSITES: dict[str, str] = {
    "youtube":       "https://www.youtube.com",
    "google":        "https://www.google.com",
    "gmail":         "https://mail.google.com",
    "github":        "https://www.github.com",
    "twitter":       "https://www.twitter.com",
    "x":             "https://www.x.com",
    "instagram":     "https://www.instagram.com",
    "linkedin":      "https://www.linkedin.com",
    "facebook":      "https://www.facebook.com",
    "reddit":        "https://www.reddit.com",
    "wikipedia":     "https://www.wikipedia.org",
    "stackoverflow": "https://stackoverflow.com",
    "netflix":       "https://www.netflix.com",
    "spotify":       "https://open.spotify.com",
    "whatsapp":      "https://web.whatsapp.com",
    "maps":          "https://maps.google.com",
    "google maps":   "https://maps.google.com",
    "drive":         "https://drive.google.com",
    "google drive":  "https://drive.google.com",
    "chat gpt":      "https://chatgpt.com",
    "chatgpt":       "https://chatgpt.com",
    "openai":        "https://www.openai.com",
    "twitch":        "https://www.twitch.tv",
    "discord":       "https://discord.com/app",
    "amazon":        "https://www.amazon.com.tr",
    "trendyol":      "https://www.trendyol.com",
    "n11":           "https://www.n11.com",
    "hepsiburada":   "https://www.hepsiburada.com",
}

# Güvenli uygulama whitelist'i — sadece bu uygulamalar açılabilir
ALLOWED_APPS: dict[str, str] = {
    # Windows uygulamaları
    "notepad":      "notepad.exe",
    "calc":         "calc.exe",
    "calculator":   "calc.exe",
    "paint":        "mspaint.exe",
    "explorer":     "explorer.exe",
    "wordpad":      "wordpad.exe",
    "cmd":          "cmd.exe",
    "powershell":   "powershell.exe",
    "chrome":       "chrome.exe",
    "firefox":      "firefox.exe",
    "edge":         "msedge.exe",
    "vscode":       "code.exe",
    "vs code":      "code.exe",
    "code":         "code.exe",
    "word":         "winword.exe",
    "excel":        "excel.exe",
    "powerpoint":   "powerpnt.exe",
    "teams":        "teams.exe",
    "outlook":      "outlook.exe",
    "spotify":      "spotify.exe",
    "vlc":          "vlc.exe",
    "discord":      "discord.exe",
    "obs":          "obs64.exe",
    "gimp":         "gimp.exe",
}


class AppServer:
    """Windows üzerinde uygulama yönetimi sağlayan MCP server."""

    def _is_windows(self) -> bool:
        return sys.platform == "win32"

    def _get_allowed_exe(self, name: str) -> str | None:
        """Uygulama adını normalize ederek whitelist'te arar."""
        normalized = name.strip().lower()
        # Tam eşleşme
        if normalized in ALLOWED_APPS:
            return ALLOWED_APPS[normalized]
        # Kısmi eşleşme (ör: 'google chrome' → 'chrome')
        for key, exe in ALLOWED_APPS.items():
            if key in normalized or normalized in key:
                return exe
        return None

    def app_open(self, name: str, file: str | None = None) -> dict[str, Any]:
        """
        Belirtilen uygulamayı başlatır.

        Args:
            name: Uygulama adı (ör: 'notepad', 'chrome', 'calculator', 'vscode')
            file: Açılacak dosya veya klasör yolu (opsiyonel, VSCode, Notepad vb. için)

        Returns:
            {"success": bool, "message": str, "pid": int | None}
        """
        if not self._is_windows():
            return {
                "success": False,
                "error": "Bu araç yalnızca Windows üzerinde çalışır.",
            }

        exe = self._get_allowed_exe(name)
        if exe is None:
            # Whitelist'te yoksa — popüler website mi? Web olarak aç
            normalized = name.strip().lower()
            if normalized in KNOWN_WEBSITES or "." in normalized:
                return self.web_open(normalized)
            allowed_list = ", ".join(sorted(ALLOWED_APPS.keys()))
            return {
                "success": False,
                "error": (
                    f"'{name}' uygulaması whitelist'te bulunmuyor. "
                    f"İzin verilen uygulamalar: {allowed_list}"
                ),
            }

        # Komut satırını oluştur
        cmd = [exe]
        if file:
            # Dosya yolunu temizle ve ekle
            file = file.strip().strip('"').strip("'")
            cmd.append(file)

        try:
            proc = subprocess.Popen(
                cmd,
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            target = f"'{file}' dosyasıyla" if file else ""
            logger.info("app_open", extra={"app": name, "exe": exe, "file": file, "pid": proc.pid})
            return {
                "success": True,
                "message": f"'{name}' ({exe}) {target} başlatıldı.",
                "pid": proc.pid,
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": f"'{exe}' çalıştırılabilir dosyası bulunamadı. Uygulama yüklü olmayabilir.",
            }
        except Exception as exc:
            logger.error(f"app_open hatası: {exc}", extra={"app": name})
            return {"success": False, "error": str(exc)}

    def app_close(self, name: str) -> dict[str, Any]:
        """
        Belirtilen uygulamayı kapatır (taskkill).

        Args:
            name: Uygulama adı (ör: 'notepad', 'chrome')

        Returns:
            {"success": bool, "message": str}
        """
        if not self._is_windows():
            return {
                "success": False,
                "error": "Bu araç yalnızca Windows üzerinde çalışır.",
            }

        exe = self._get_allowed_exe(name)
        if exe is None:
            return {
                "success": False,
                "error": f"'{name}' uygulaması whitelist'te bulunmuyor.",
            }

        try:
            result = subprocess.run(
                ["taskkill", "/F", "/IM", exe],
                capture_output=True,
                text=True,
                shell=False,
            )
            if result.returncode == 0:
                logger.warning("app_close", extra={"app": name, "exe": exe})
                return {
                    "success": True,
                    "message": f"'{name}' ({exe}) kapatıldı.",
                }
            else:
                return {
                    "success": False,
                    "error": f"Kapatma başarısız: {result.stderr.strip()}",
                }
        except Exception as exc:
            logger.error(f"app_close hatası: {exc}", extra={"app": name})
            return {"success": False, "error": str(exc)}

    def app_list_running(self) -> dict[str, Any]:
        """
        Şu anda çalışan uygulamaları listeler (whitelist ile eşleşenleri).

        Returns:
            {"success": bool, "apps": list[dict]}
        """
        if not self._is_windows():
            return {
                "success": False,
                "error": "Bu araç yalnızca Windows üzerinde çalışır.",
            }

        try:
            result = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                shell=False,
            )

            running_apps = []
            allowed_exes = {exe.lower() for exe in ALLOWED_APPS.values()}

            for line in result.stdout.strip().splitlines():
                # CSV format: "notepad.exe","12345","Console","1","10,000 K"
                parts = line.strip('"').split('","')
                if not parts:
                    continue
                exe_name = parts[0].lower()
                pid = parts[1] if len(parts) > 1 else "?"
                mem = parts[4].replace('"', '') if len(parts) > 4 else "?"

                if exe_name in allowed_exes:
                    # İsim bul
                    friendly_name = next(
                        (k for k, v in ALLOWED_APPS.items() if v.lower() == exe_name),
                        exe_name
                    )
                    running_apps.append({
                        "name": friendly_name,
                        "exe": exe_name,
                        "pid": pid,
                        "memory": mem,
                    })

            logger.info("app_list_running", extra={"count": len(running_apps)})
            return {
                "success": True,
                "apps": running_apps,
                "total": len(running_apps),
            }

        except Exception as exc:
            logger.error(f"app_list_running hatası: {exc}")
            return {"success": False, "error": str(exc)}
    def web_open(self, url: str) -> dict[str, Any]:
        """
        Belirtilen URL veya site adını varsayılan tarayıcıda açar.

        Args:
            url: Web adresi (https://youtube.com) VEYA kısa isim (youtube, google vb.)

        Returns:
            {"success": bool, "message": str, "url": str}
        """
        url = url.strip().strip('"').strip("'")

        # 1. Kısa isim mi? → KNOWN_WEBSITES'ten tam URL'e çevir
        normalized = url.lower().rstrip("/")
        if normalized in KNOWN_WEBSITES:
            url = KNOWN_WEBSITES[normalized]
        elif not url.startswith(("http://", "https://")):
            # 2. Protokol eksik ama domain-like (nokta var) → https:// ekle
            if "." in url:
                url = "https://" + url
            else:
                # 3. Sadece kelime → google'da ara
                url = f"https://www.google.com/search?q={url.replace(' ', '+')}"

        try:
            opened = webbrowser.open(url)
            if opened:
                logger.info("web_open", extra={"url": url})
                return {
                    "success": True,
                    "message": f"'{url}' varsayılan tarayıcıda açıldı.",
                    "url": url,
                }
            else:
                return {
                    "success": False,
                    "error": "Tarayıcı açılamadı.",
                }
        except Exception as exc:
            logger.error(f"web_open hatası: {exc}", extra={"url": url})
            return {"success": False, "error": str(exc)}


app_server = AppServer()
