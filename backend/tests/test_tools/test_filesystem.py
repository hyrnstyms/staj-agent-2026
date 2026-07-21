"""
tests/test_tools/test_filesystem.py
-------------------------------------
Dosya sistemi MCP server'ı unit testleri.

Tüm testler geçici dizinde (tmp_path) çalışır — gerçek sandbox'a dokunmaz.
LLM gerektirmez.

Test senaryoları:
    - file_read: normal okuma, bulunamadı, dizin okuma hatası
    - file_write: yeni dosya, üzerine yazma, alt dizin oluşturma
    - file_delete: silme, bulunamadı, dizin silme hatası
    - file_list: liste, boş dizin, bulunamadı
    - file_move: taşıma, yeniden adlandırma, bulunamadı
    - Güvenlik: path traversal ../../ reddedilmeli
"""

import pytest
from pathlib import Path

from mcp_servers.filesystem_server import FilesystemServer, SandboxViolationError


@pytest.fixture
def fs(tmp_path) -> FilesystemServer:
    """Her test için ayrı FilesystemServer (tmp sandbox)."""
    return FilesystemServer(sandbox_root=tmp_path / "sandbox")


@pytest.fixture
def sample_files(fs: FilesystemServer) -> dict[str, str]:
    """Demo dosyaları oluşturur ve path → content haritası döner."""
    files = {
        "hello.txt":         "Merhaba Dünya!",
        "data.json":         '{"key": "value"}',
        "subdir/nested.txt": "Alt dizindeki dosya",
    }
    for rel_path, content in files.items():
        abs_path = fs.sandbox_root / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(content, encoding="utf-8")
    return files


# ─────────────────────────────────────────────────────────────────────────────
# file_read
# ─────────────────────────────────────────────────────────────────────────────

class TestFileRead:
    def test_read_existing_file(self, fs, sample_files):
        result = fs.file_read("hello.txt")
        assert result["success"] is True
        assert result["content"] == "Merhaba Dünya!"
        assert result["size_bytes"] > 0

    def test_read_returns_relative_path(self, fs, sample_files):
        result = fs.file_read("hello.txt")
        assert result["path"] == "hello.txt"

    def test_read_nested_file(self, fs, sample_files):
        result = fs.file_read("subdir/nested.txt")
        assert result["content"] == "Alt dizindeki dosya"

    def test_read_nonexistent_raises(self, fs):
        with pytest.raises(FileNotFoundError):
            fs.file_read("yok.txt")

    def test_read_directory_raises(self, fs, sample_files):
        with pytest.raises(IsADirectoryError):
            fs.file_read("subdir")

    def test_read_path_traversal_raises(self, fs):
        """../../etc/passwd gibi path traversal sandbox ihlali olmalı."""
        with pytest.raises(SandboxViolationError):
            fs.file_read("../../etc/passwd")

    def test_read_absolute_outside_sandbox_raises(self, fs, tmp_path):
        """Sandbox dışı mutlak path reddedilmeli."""
        outside = tmp_path / "outside.txt"
        outside.write_text("dışarıdaki dosya")
        with pytest.raises(SandboxViolationError):
            fs.file_read(str(outside))


# ─────────────────────────────────────────────────────────────────────────────
# file_write
# ─────────────────────────────────────────────────────────────────────────────

class TestFileWrite:
    def test_write_new_file(self, fs):
        result = fs.file_write("yeni.txt", "İçerik")
        assert result["success"] is True
        assert result["created"] is True
        assert (fs.sandbox_root / "yeni.txt").read_text(encoding="utf-8") == "İçerik"

    def test_overwrite_existing(self, fs, sample_files):
        result = fs.file_write("hello.txt", "Yeni içerik")
        assert result["created"] is False
        assert (fs.sandbox_root / "hello.txt").read_text(encoding="utf-8") == "Yeni içerik"

    def test_write_creates_parent_dirs(self, fs):
        result = fs.file_write("a/b/c/deep.txt", "derin")
        assert result["success"] is True
        assert (fs.sandbox_root / "a/b/c/deep.txt").exists()

    def test_write_size_returned(self, fs):
        content = "abc" * 100
        result = fs.file_write("size_test.txt", content)
        assert result["size_bytes"] == len(content.encode("utf-8"))

    def test_write_traversal_raises(self, fs):
        with pytest.raises(SandboxViolationError):
            fs.file_write("../../evil.txt", "kötü içerik")


# ─────────────────────────────────────────────────────────────────────────────
# file_delete
# ─────────────────────────────────────────────────────────────────────────────

class TestFileDelete:
    def test_delete_existing(self, fs, sample_files):
        result = fs.file_delete("hello.txt")
        assert result["success"] is True
        assert not (fs.sandbox_root / "hello.txt").exists()

    def test_delete_nonexistent_raises(self, fs):
        with pytest.raises(FileNotFoundError):
            fs.file_delete("yok.txt")

    def test_delete_directory_raises(self, fs, sample_files):
        with pytest.raises(IsADirectoryError):
            fs.file_delete("subdir")

    def test_delete_traversal_raises(self, fs):
        with pytest.raises(SandboxViolationError):
            fs.file_delete("../../important.txt")


# ─────────────────────────────────────────────────────────────────────────────
# file_list
# ─────────────────────────────────────────────────────────────────────────────

class TestFileList:
    def test_list_root(self, fs, sample_files):
        result = fs.file_list()
        assert result["success"] is True
        names = [item["name"] for item in result["items"]]
        assert "hello.txt" in names
        assert "subdir" in names

    def test_list_subdirectory(self, fs, sample_files):
        result = fs.file_list("subdir")
        names = [item["name"] for item in result["items"]]
        assert "nested.txt" in names

    def test_list_empty_dir(self, fs):
        (fs.sandbox_root / "boş").mkdir()
        result = fs.file_list("boş")
        assert result["total"] == 0
        assert result["items"] == []

    def test_list_nonexistent_raises(self, fs):
        with pytest.raises(FileNotFoundError):
            fs.file_list("yok_dizin")

    def test_list_file_type_info(self, fs, sample_files):
        result = fs.file_list()
        items_by_name = {i["name"]: i for i in result["items"]}
        assert items_by_name["hello.txt"]["type"] == "file"
        assert items_by_name["subdir"]["type"] == "directory"
        assert items_by_name["hello.txt"]["size_bytes"] > 0

    def test_list_traversal_raises(self, fs):
        with pytest.raises(SandboxViolationError):
            fs.file_list("../../")


# ─────────────────────────────────────────────────────────────────────────────
# file_move
# ─────────────────────────────────────────────────────────────────────────────

class TestFileMove:
    def test_rename_file(self, fs, sample_files):
        result = fs.file_move("hello.txt", "merhaba.txt")
        assert result["success"] is True
        assert not (fs.sandbox_root / "hello.txt").exists()
        assert (fs.sandbox_root / "merhaba.txt").exists()

    def test_move_to_subdir(self, fs, sample_files):
        (fs.sandbox_root / "hedef").mkdir()
        result = fs.file_move("hello.txt", "hedef/hello.txt")
        assert (fs.sandbox_root / "hedef/hello.txt").exists()

    def test_move_creates_parent(self, fs, sample_files):
        result = fs.file_move("hello.txt", "yeni_dizin/hello.txt")
        assert (fs.sandbox_root / "yeni_dizin/hello.txt").exists()

    def test_move_nonexistent_raises(self, fs):
        with pytest.raises(FileNotFoundError):
            fs.file_move("yok.txt", "hedef.txt")

    def test_move_src_traversal_raises(self, fs):
        with pytest.raises(SandboxViolationError):
            fs.file_move("../../src.txt", "hedef.txt")

    def test_move_dst_traversal_raises(self, fs, sample_files):
        with pytest.raises(SandboxViolationError):
            fs.file_move("hello.txt", "../../evil.txt")


# ─────────────────────────────────────────────────────────────────────────────
# Sandbox Güvenlik Testleri
# ─────────────────────────────────────────────────────────────────────────────

class TestSandboxSecurity:
    """Path traversal ve sandbox sınırı testleri."""

    TRAVERSAL_PATHS = [
        "../../etc/passwd",
        "../outside.txt",
        "subdir/../../../etc/hosts",
        "a/b/../../../../../../tmp/evil",
    ]

    @pytest.mark.parametrize("path", TRAVERSAL_PATHS)
    def test_read_traversal_paths(self, fs, path):
        with pytest.raises(SandboxViolationError):
            fs.file_read(path)

    @pytest.mark.parametrize("path", TRAVERSAL_PATHS)
    def test_write_traversal_paths(self, fs, path):
        with pytest.raises(SandboxViolationError):
            fs.file_write(path, "evil")

    @pytest.mark.parametrize("path", TRAVERSAL_PATHS)
    def test_delete_traversal_paths(self, fs, path):
        with pytest.raises(SandboxViolationError):
            fs.file_delete(path)

    def test_safe_path_stays_in_sandbox(self, fs):
        """Güvenli path doğru çözülmeli."""
        safe = fs._safe_path("hello.txt")
        assert str(safe).startswith(str(fs.sandbox_root))

    def test_sandbox_info(self, fs):
        info = fs.get_sandbox_info()
        assert "sandbox_root" in info
        assert info["disk_total_gb"] > 0
