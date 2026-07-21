"""
mcp_servers/filesystem_server.py
---------------------------------
Dosya sistemi MCP server'ı.

Güvenlik Modeli:
    ✅  Tüm işlemler yalnızca SANDBOX_ROOT dizini altında çalışır.
    ✅  Path traversal saldırıları (../../etc/passwd) reddedilir.
    ✅  Sembolik link takibi yapılmaz (symlink SANDBOX_ROOT dışına çıkarsa reddedilir).
    ✅  Geri döndürülemez işlemler (file_write, file_delete, file_move)
        izin ve onay kontrolü gerektirir (tool_executor.py üzerinden sağlanır).

Tool'lar:
    - file_read(path)           → str
    - file_write(path, content) → dict
    - file_delete(path)         → dict
    - file_list(directory="")   → list[dict]
    - file_move(src, dst)       → dict

Kullanım:
    from mcp_servers.filesystem_server import FilesystemServer

    fs = FilesystemServer()
    result = fs.file_read("README.md")
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from config import settings
from core.logger import get_logger

logger = get_logger(__name__)


class SandboxViolationError(PermissionError):
    """
    Path traversal veya sandbox dışı erişim girişimi.

    Bu hata yalnızca güvenlik ihlallerinde fırlatılır,
    sıradan "dosya bulunamadı" durumlarında değil.
    """


class FilesystemServer:
    """
    Sandbox korumalı dosya sistemi tool koleksiyonu.

    Tüm path argümanları `_safe_path()` ile doğrulanır:
        - Mutlak path'e çevrilir (resolve)
        - SANDBOX_ROOT altında olup olmadığı kontrol edilir
        - Dışarı çıkıyorsa SandboxViolationError fırlatılır
    """

    def __init__(self, sandbox_root: Path | None = None) -> None:
        self.sandbox_root: Path = (sandbox_root or settings.SANDBOX_ROOT).resolve()
        self.sandbox_root.mkdir(parents=True, exist_ok=True)
        logger.info(
            f"FilesystemServer başlatıldı",
            extra={"sandbox_root": str(self.sandbox_root)},
        )

    # ── Güvenlik ─────────────────────────────────────────────────────────────

    def _safe_path(self, user_path: str | Path) -> Path:
        """
        Kullanıcı tarafından verilen path'i güvenli şekilde çözer.

        1. SANDBOX_ROOT ile birleştirir (mutlak path ise birleştime yapmaz,
           ama zaten SANDBOX_ROOT altında olması gerekir).
        2. `resolve()` ile sembolik linkleri ve .. bileşenlerini çözer.
        3. Sonuç SANDBOX_ROOT altında değilse SandboxViolationError fırlatır.

        Args:
            user_path: Kullanıcıdan gelen dosya/dizin yolu

        Returns:
            Güvenli, mutlak Path nesnesi

        Raises:
            SandboxViolationError: Path sandbox dışına çıkıyorsa
        """
        # Mutlak yol ise doğrudan kullan, değilse sandbox'a göreli kabul et
        p = Path(user_path)
        if not p.is_absolute():
            p = self.sandbox_root / p

        # Sembolik linkler ve .. bileşenlerini çöz
        try:
            resolved = p.resolve()
        except OSError as exc:
            raise SandboxViolationError(
                f"Path çözümlenemedi: {user_path!r} — {exc}"
            ) from exc

        # SANDBOX_ROOT altında mı?
        try:
            resolved.relative_to(self.sandbox_root)
        except ValueError:
            raise SandboxViolationError(
                f"⛔  Güvenlik İhlali: '{user_path}' yolu sandbox dışına çıkıyor.\n"
                f"    İzin verilen alan: {self.sandbox_root}\n"
                f"    İstenen path   : {resolved}"
            )

        return resolved

    # ── Tool Metodları ────────────────────────────────────────────────────────

    def file_read(self, path: str) -> dict[str, Any]:
        """
        Dosya içeriğini okur ve döner.

        Args:
            path: Okunacak dosyanın yolu (sandbox içinde)

        Returns:
            {"success": True, "path": str, "content": str, "size_bytes": int}

        Raises:
            SandboxViolationError : Path sandbox dışına çıkıyorsa
            FileNotFoundError     : Dosya yoksa
            PermissionError       : Dosya okunamıyorsa
        """
        safe = self._safe_path(path)

        if not safe.exists():
            raise FileNotFoundError(f"Dosya bulunamadı: {path!r}")
        if not safe.is_file():
            raise IsADirectoryError(f"Belirtilen yol bir dosya değil, dizin: {path!r}")

        content = safe.read_text(encoding="utf-8", errors="replace")
        size = safe.stat().st_size

        logger.info(
            f"file_read",
            extra={"path": str(safe), "size_bytes": size},
        )

        return {
            "success": True,
            "path": str(safe.relative_to(self.sandbox_root)),
            "content": content,
            "size_bytes": size,
        }

    def file_write(self, path: str, content: str) -> dict[str, Any]:
        """
        Dosya oluşturur veya üzerine yazar.

        ⚠️  Bu işlem onay gerektirir (tool_executor.py tarafından kontrol edilir).

        Args:
            path   : Yazılacak dosya yolu
            content: Dosya içeriği

        Returns:
            {"success": True, "path": str, "size_bytes": int, "created": bool}
        """
        safe = self._safe_path(path)
        safe.parent.mkdir(parents=True, exist_ok=True)

        was_existing = safe.exists()
        safe.write_text(content, encoding="utf-8")
        size = safe.stat().st_size

        action = "güncellendi" if was_existing else "oluşturuldu"
        logger.info(
            f"file_write — {action}",
            extra={"path": str(safe), "size_bytes": size},
        )

        return {
            "success": True,
            "path": str(safe.relative_to(self.sandbox_root)),
            "size_bytes": size,
            "created": not was_existing,
        }

    def file_delete(self, path: str) -> dict[str, Any]:
        """
        Dosyayı kalıcı olarak siler.

        ⚠️  Bu işlem onay gerektirir (tool_executor.py tarafından kontrol edilir).
        ⚠️  Silme geri alınamaz.

        Args:
            path: Silinecek dosya yolu

        Returns:
            {"success": True, "path": str, "deleted": str}

        Raises:
            FileNotFoundError: Dosya yoksa
        """
        safe = self._safe_path(path)

        if not safe.exists():
            raise FileNotFoundError(f"Silinecek dosya bulunamadı: {path!r}")
        if not safe.is_file():
            raise IsADirectoryError(
                f"file_delete yalnızca dosyaları siler. Dizin silmek için ayrı bir komut kullanın: {path!r}"
            )

        size = safe.stat().st_size
        safe.unlink()

        logger.warning(
            f"file_delete — dosya silindi",
            extra={"path": str(safe), "size_bytes": size},
        )

        return {
            "success": True,
            "path": str(safe.relative_to(self.sandbox_root)),
            "deleted": path,
        }

    def file_list(self, directory: str = "") -> dict[str, Any]:
        """
        Dizin içeriğini listeler.

        Args:
            directory: Listelenecek dizin (boş bırakılırsa sandbox kökü)

        Returns:
            {"success": True, "directory": str, "items": list[dict], "total": int}
        """
        dir_path = directory if directory else "."
        safe = self._safe_path(dir_path)

        if not safe.exists():
            raise FileNotFoundError(f"Dizin bulunamadı: {directory!r}")
        if not safe.is_dir():
            raise NotADirectoryError(f"Belirtilen yol dizin değil: {directory!r}")

        items = []
        for entry in sorted(safe.iterdir()):
            try:
                stat = entry.stat()
                items.append(
                    {
                        "name": entry.name,
                        "type": "directory" if entry.is_dir() else "file",
                        "size_bytes": stat.st_size if entry.is_file() else None,
                        "path": str(entry.relative_to(self.sandbox_root)),
                    }
                )
            except OSError:
                continue  # İzin hatası olan girişleri atla

        logger.info(
            f"file_list",
            extra={"directory": str(safe), "count": len(items)},
        )

        return {
            "success": True,
            "directory": str(safe.relative_to(self.sandbox_root)),
            "items": items,
            "total": len(items),
        }

    def file_move(self, src: str, dst: str) -> dict[str, Any]:
        """
        Dosyayı taşır veya yeniden adlandırır.

        ⚠️  Bu işlem onay gerektirir (tool_executor.py tarafından kontrol edilir).

        Args:
            src: Kaynak dosya yolu
            dst: Hedef dosya yolu

        Returns:
            {"success": True, "src": str, "dst": str}

        Raises:
            FileNotFoundError     : Kaynak dosya yoksa
            SandboxViolationError : Kaynak veya hedef sandbox dışına çıkıyorsa
        """
        safe_src = self._safe_path(src)
        safe_dst = self._safe_path(dst)

        if not safe_src.exists():
            raise FileNotFoundError(f"Kaynak dosya bulunamadı: {src!r}")

        safe_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(safe_src), str(safe_dst))

        logger.info(
            f"file_move",
            extra={"src": str(safe_src), "dst": str(safe_dst)},
        )

        return {
            "success": True,
            "src": str(safe_src.relative_to(self.sandbox_root)),
            "dst": str(safe_dst.relative_to(self.sandbox_root)),
        }

    def get_sandbox_info(self) -> dict[str, Any]:
        """Sandbox hakkında bilgi döner (sağlık kontrolü için)."""
        total, used, free = shutil.disk_usage(self.sandbox_root)
        return {
            "sandbox_root": str(self.sandbox_root),
            "disk_total_gb": round(total / (1024**3), 2),
            "disk_used_gb":  round(used  / (1024**3), 2),
            "disk_free_gb":  round(free  / (1024**3), 2),
        }


# Modül genelinde kullanılan tekil server örneği
filesystem_server = FilesystemServer()
