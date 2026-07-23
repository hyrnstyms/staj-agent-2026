"""
integrations/github_tools.py
-----------------------------
GitHub entegrasyonu — mcp_servers/code_server.py'deki git fonksiyonlarına
erişim sağlayan convenience wrapper'lar.

Not: Gerçek implementasyon mcp_servers/code_server.py'dedir.
Bu modül dışarıdan kolay import için arayüz sağlar.
"""

from __future__ import annotations

from typing import Any

from mcp_servers.code_server import code_server


def git_status(repo_path: str) -> dict[str, Any]:
    """Git reposunun değişiklik durumunu gösterir."""
    return code_server.git_status(repo_path)


def git_diff_preview(repo_path: str) -> dict[str, Any]:
    """Yapılan değişikliklerin özetini gösterir."""
    return code_server.git_diff_preview(repo_path)


def git_create_branch(repo_path: str, branch_name: str) -> dict[str, Any]:
    """Yeni git branch'i oluşturur."""
    return code_server.git_create_branch(repo_path, branch_name)


def git_commit_and_push(repo_path: str, message: str, branch: str) -> dict[str, Any]:
    """Commit oluşturur ve push eder. ⚠️ Onay gerektirir."""
    return code_server.git_commit_and_push(repo_path, message, branch)


def github_create_pull_request(repo: str, branch: str, title: str) -> dict[str, Any]:
    """GitHub'da Pull Request açar. ⚠️ Onay gerektirir."""
    return code_server.github_create_pull_request(repo, branch, title)
