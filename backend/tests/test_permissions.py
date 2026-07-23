"""
tests/test_permissions.py
-------------------------
Merkezi RBAC modülü testleri.

Test matrisi:
    - employee: dosya okuma ✓, dosya silme ✗, db_delete ✗
    - hr: dosya silme (onay ile) ✓, db_delete ✗, approve_leave ✓
    - admin: tüm tool'lar ✓
    - pasif kullanıcı: her şey ✗

Doğrudan DB tablosuna dayanan testler — LLM gerektirmez.
"""

from core.permissions import permission_manager, PermissionResult


class TestEmployeePermissions:
    """employee rolü için izin testleri."""

    def test_file_read_allowed(self, db):
        result = permission_manager.check(user_role="employee", tool_name="file_read", db=db)
        assert result.allowed is True
        assert result.requires_approval is False

    def test_file_write_requires_approval(self, db):
        result = permission_manager.check(user_role="employee", tool_name="file_write", db=db)
        assert result.allowed is True
        assert result.requires_approval is True

    def test_file_delete_denied(self, db):
        result = permission_manager.check(user_role="employee", tool_name="file_delete", db=db)
        assert result.allowed is False
        assert result.reason != ""

    def test_file_list_allowed(self, db):
        result = permission_manager.check(user_role="employee", tool_name="file_list", db=db)
        assert result.allowed is True
        assert result.requires_approval is False

    def test_db_delete_denied(self, db):
        result = permission_manager.check(user_role="employee", tool_name="db_delete", db=db)
        assert result.allowed is False

    def test_db_list_tables_denied(self, db):
        result = permission_manager.check(user_role="employee", tool_name="db_list_tables", db=db)
        assert result.allowed is False

    def test_approve_leave_denied(self, db):
        result = permission_manager.check(user_role="employee", tool_name="approve_leave", db=db)
        assert result.allowed is False

    def test_request_leave_allowed_with_approval(self, db):
        result = permission_manager.check(user_role="employee", tool_name="request_leave", db=db)
        assert result.allowed is True
        assert result.requires_approval is True

    def test_git_commit_allowed_with_approval(self, db):
        result = permission_manager.check(user_role="employee", tool_name="git_commit_and_push", db=db)
        assert result.allowed is True
        assert result.requires_approval is True


class TestHrPermissions:
    """hr rolü için izin testleri."""

    def test_file_delete_with_approval(self, db):
        result = permission_manager.check(user_role="hr", tool_name="file_delete", db=db)
        assert result.allowed is True
        assert result.requires_approval is True

    def test_db_delete_denied(self, db):
        """HR bile db_delete yapamaz."""
        result = permission_manager.check(user_role="hr", tool_name="db_delete", db=db)
        assert result.allowed is False

    def test_approve_leave_with_approval(self, db):
        result = permission_manager.check(user_role="hr", tool_name="approve_leave", db=db)
        assert result.allowed is True
        assert result.requires_approval is True

    def test_db_query_allowed(self, db):
        result = permission_manager.check(user_role="hr", tool_name="db_query", db=db)
        assert result.allowed is True

    def test_code_run_denied(self, db):
        """HR kod çalıştıramaz."""
        result = permission_manager.check(user_role="hr", tool_name="code_run", db=db)
        assert result.allowed is False


class TestAdminPermissions:
    """admin rolü için izin testleri."""

    def test_file_delete_with_approval(self, db):
        result = permission_manager.check(user_role="admin", tool_name="file_delete", db=db)
        assert result.allowed is True
        assert result.requires_approval is True

    def test_db_delete_with_approval(self, db):
        result = permission_manager.check(user_role="admin", tool_name="db_delete", db=db)
        assert result.allowed is True
        assert result.requires_approval is True

    def test_git_commit_with_approval(self, db):
        result = permission_manager.check(user_role="admin", tool_name="git_commit_and_push", db=db)
        assert result.allowed is True
        assert result.requires_approval is True

    def test_file_write_no_approval(self, db):
        """Admin dosya yazma için onay gerektirmez."""
        result = permission_manager.check(user_role="admin", tool_name="file_write", db=db)
        assert result.allowed is True
        assert result.requires_approval is False

    def test_app_list_allowed(self, db):
        result = permission_manager.check(user_role="admin", tool_name="app_list_running", db=db)
        assert result.allowed is True

    def test_calendar_add_no_approval(self, db):
        result = permission_manager.check(user_role="admin", tool_name="calendar_add_event", db=db)
        assert result.allowed is True
        assert result.requires_approval is False


class TestUnknownRole:
    """Bilinmeyen rol ve tool testleri."""

    def test_unknown_role_denied(self, db):
        result = permission_manager.check(user_role="superuser", tool_name="file_read", db=db)
        assert result.allowed is False
        assert "tanımlanmamış" in result.reason or "bulunamadı" in result.reason.lower()

    def test_unknown_tool_denied(self, db):
        result = permission_manager.check(user_role="admin", tool_name="nonexistent_tool", db=db)
        assert result.allowed is False

    def test_unknown_both_denied(self, db):
        result = permission_manager.check(user_role="superuser", tool_name="super_tool", db=db)
        assert result.allowed is False


class TestCheckByUserId:
    """user_id tabanlı izin kontrolü testleri."""

    def test_employee_user_file_read(self, db):
        result = permission_manager.check_by_user_id(user_id=1, tool_name="file_read", db=db)
        assert result.allowed is True

    def test_employee_user_db_delete_denied(self, db):
        result = permission_manager.check_by_user_id(user_id=1, tool_name="db_delete", db=db)
        assert result.allowed is False

    def test_hr_user_approve_leave(self, db):
        result = permission_manager.check_by_user_id(user_id=2, tool_name="approve_leave", db=db)
        assert result.allowed is True

    def test_admin_user_all_allowed(self, db):
        result = permission_manager.check_by_user_id(user_id=3, tool_name="db_delete", db=db)
        assert result.allowed is True

    def test_inactive_user_denied(self, db):
        """Pasif kullanıcı her şeyden men edilir."""
        result = permission_manager.check_by_user_id(user_id=4, tool_name="file_read", db=db)
        assert result.allowed is False
        assert "aktif değil" in result.reason

    def test_nonexistent_user_denied(self, db):
        result = permission_manager.check_by_user_id(user_id=9999, tool_name="file_read", db=db)
        assert result.allowed is False
        assert "bulunamadı" in result.reason


class TestPermissionResult:
    """PermissionResult dataclass testleri."""

    def test_allowed_result_attributes(self, db):
        result = permission_manager.check(user_role="admin", tool_name="file_read", db=db)
        assert isinstance(result, PermissionResult)
        assert result.allowed is True
        assert result.role == "admin"
        assert result.tool_name == "file_read"
        assert result.reason == ""

    def test_denied_result_attributes(self, db):
        result = permission_manager.check(user_role="employee", tool_name="db_delete", db=db)
        assert isinstance(result, PermissionResult)
        assert result.allowed is False
        assert result.reason != ""
        assert result.tool_name == "db_delete"
