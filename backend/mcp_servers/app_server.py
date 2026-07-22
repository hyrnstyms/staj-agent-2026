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
from typing import Any

from core.logger import get_logger

logger = get_logger(__name__)

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

    def app_open(self, name: str) -> dict[str, Any]:
        """
        Belirtilen uygulamayı başlatır.

        Args:
            name: Uygulama adı (ör: 'notepad', 'chrome', 'calculator')

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
            allowed_list = ", ".join(sorted(ALLOWED_APPS.keys()))
            return {
                "success": False,
                "error": (
                    f"'{name}' uygulaması whitelist'te bulunmuyor. "
                    f"İzin verilen uygulamalar: {allowed_list}"
                ),
            }

        try:
            proc = subprocess.Popen(
                [exe],
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("app_open", extra={"app": name, "exe": exe, "pid": proc.pid})
            return {
                "success": True,
                "message": f"'{name}' ({exe}) başlatıldı.",
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


app_server = AppServer()
