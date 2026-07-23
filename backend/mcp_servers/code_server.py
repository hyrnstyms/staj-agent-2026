"""
mcp_servers/code_server.py
--------------------------
Faz 3: Docker Sandbox ve Kod/Git MCP Server
Güvenlik odaklı tam implementasyon.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any
import requests

from config import settings
from core.logger import get_logger

logger = get_logger(__name__)


class SandboxViolationError(PermissionError):
    """Path traversal veya izin verilmeyen repolara erişim denemesi."""


ALLOWED_IMAGES = {
    "python": "python:3.10-slim",
    "javascript": "node:20-slim",
    "bash": "alpine:3.19"
}

def _build_docker_command(host_path: str, container_path: str, image: str, command: list[str]) -> list[str]:
    """
    Güvenlik sınırları belirlenmiş (hardened) Docker çalıştırma komutu oluşturur.
    Hiçbir şekilde dışarıdan override edilemez.
    """
    base_cmd = [
        "docker", "run", "--rm",
        "--network", "none",
        "--memory=256m",
        "--cpus=0.5",
        "--pids-limit=50",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--read-only",
        "-v", f"{host_path}:{container_path}:rw",
        image
    ]
    return base_cmd + command


class CodeServer:
    def __init__(self, sandbox_root: Path | None = None):
        self.sandbox_root = (sandbox_root or settings.SANDBOX_ROOT).resolve()

    def _safe_path(self, user_path: str) -> Path:
        """Dosya yolunun sandbox içerisinde olduğunu doğrular."""
        if os.path.isabs(user_path):
            target = Path(user_path).resolve()
        else:
            target = (self.sandbox_root / user_path).resolve()

        try:
            target.relative_to(self.sandbox_root)
        except ValueError:
            raise SandboxViolationError(f"Güvenlik İhlali: {user_path} Sandbox dışına çıkamaz.")
        return target
        
    def _safe_repo(self, repo_path: str) -> Path:
        """Repo yolunun hem sandbox içerisinde hem de ALLOWED_REPOS listesinde olduğunu doğrular."""
        target = self._safe_path(repo_path)
        
        allowed_repos = settings.allowed_repos_list
        if not allowed_repos:
            # Eğer ALLOWED_REPOS boşsa güvenlik gereği hiçbir repoya izin verme
            raise SandboxViolationError("Sistemde yapılandırılmış ALLOWED_REPOS bulunamadı.")
            
        for allowed in allowed_repos:
            try:
                target.relative_to(allowed)
                return target
            except ValueError:
                if target == allowed:
                    return target
        
        raise SandboxViolationError(f"Güvenlik İhlali: {repo_path} ALLOWED_REPOS listesinde değil.")

    def _truncate_output(self, output: str, limit: int = 4000) -> str:
        """Çıktı çok uzunsa keser."""
        if output and len(output) > limit:
            return output[:limit] + "\n... [çıktı kesildi]"
        return output or ""

    def code_run(self, path: str, language: str) -> dict[str, Any]:
        """
        Kodu Docker sandbox'ta çalıştırır. (Onay gerekmez)
        """
        if language not in ALLOWED_IMAGES:
            return {"success": False, "error": f"Desteklenmeyen dil: {language}. İzin verilenler: {list(ALLOWED_IMAGES.keys())}"}
        
        try:
            target_file = self._safe_path(path)
            if not target_file.is_file():
                return {"success": False, "error": f"Dosya bulunamadı: {path}"}
                
            image = ALLOWED_IMAGES[language]
            host_dir = str(target_file.parent)
            container_dir = "/workspace"
            file_name = target_file.name
            
            # Dil için komut belirleme
            if language == "python":
                command = ["python", f"{container_dir}/{file_name}"]
            elif language == "javascript":
                command = ["node", f"{container_dir}/{file_name}"]
            elif language == "bash":
                command = ["sh", f"{container_dir}/{file_name}"]
                
            docker_cmd = _build_docker_command(host_dir, container_dir, image, command)
            
            # Docker komutunu çalıştır
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=30,
                shell=False
            )
            
            stdout = self._truncate_output(result.stdout)
            stderr = self._truncate_output(result.stderr)
            
            logger.info("code_run executed", extra={"path": path, "lang": language, "returncode": result.returncode})
            
            return {
                "success": result.returncode == 0,
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": result.returncode
            }
            
        except SandboxViolationError as exc:
            return {"success": False, "error": str(exc)}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Çalıştırma zaman aşımına uğradı (30s)."}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def code_lint(self, path: str) -> dict[str, Any]:
        """Dosyadaki sözdizim hatalarını kontrol eder."""
        try:
            target_file = self._safe_path(path)
            if not target_file.is_file():
                return {"success": False, "error": f"Dosya bulunamadı: {path}"}
                
            ext = target_file.suffix.lower()
            if ext == ".py":
                # flake8 yüklüyse flake8, değilse python -m py_compile fallback
                cmd = ["flake8", str(target_file)]
                try:
                    res = subprocess.run(cmd, capture_output=True, text=True, shell=False)
                except FileNotFoundError:
                    # fallback
                    cmd = ["python", "-m", "py_compile", str(target_file)]
                    res = subprocess.run(cmd, capture_output=True, text=True, shell=False)
                    
            elif ext == ".js":
                cmd = ["node", "--check", str(target_file)]
                res = subprocess.run(cmd, capture_output=True, text=True, shell=False)
            else:
                return {"success": False, "error": f"Linter desteklenmiyor: {ext}"}
                
            stdout = self._truncate_output(res.stdout)
            stderr = self._truncate_output(res.stderr)
            
            return {
                "success": res.returncode == 0,
                "output": stdout or stderr or "Syntax OK."
            }
            
        except SandboxViolationError as exc:
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _run_git_cmd(self, repo_path: Path, cmd: list[str]) -> dict[str, Any]:
        """Yerel git CLI aracını kullanarak git komutu çalıştırır."""
        try:
            result = subprocess.run(
                ["git"] + cmd,
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                shell=False
            )
            return {
                "success": result.returncode == 0,
                "output": self._truncate_output(result.stdout),
                "error": self._truncate_output(result.stderr),
                "exit_code": result.returncode
            }
        except FileNotFoundError:
            return {"success": False, "error": "Sistemde 'git' komutu bulunamadı.", "output": "", "exit_code": -1}
        except Exception as exc:
            return {"success": False, "error": str(exc), "output": "", "exit_code": -1}

    def git_status(self, repo_path: str) -> dict[str, Any]:
        """Git reposundaki değişiklik durumunu gösterir."""
        try:
            target_repo = self._safe_repo(repo_path)
            return self._run_git_cmd(target_repo, ["status", "-s"])
        except SandboxViolationError as exc:
            return {"success": False, "error": str(exc)}

    def git_diff_preview(self, repo_path: str) -> dict[str, Any]:
        """Bekleyen değişikliklerin özetini gösterir (push yapmaz)."""
        try:
            target_repo = self._safe_repo(repo_path)
            res_unstaged = self._run_git_cmd(target_repo, ["diff"])
            res_staged = self._run_git_cmd(target_repo, ["diff", "--cached"])
            
            output = ""
            if res_staged["success"] and res_staged["output"]:
                output += "--- STAGED CHANGES ---\n" + res_staged["output"] + "\n"
            if res_unstaged["success"] and res_unstaged["output"]:
                output += "--- UNSTAGED CHANGES ---\n" + res_unstaged["output"]
                
            return {"success": True, "output": output or "Değişiklik yok."}
        except SandboxViolationError as exc:
            return {"success": False, "error": str(exc)}

    def git_create_branch(self, repo_path: str, branch_name: str) -> dict[str, Any]:
        """Yeni bir branch oluşturur ve geçiş yapar."""
        try:
            target_repo = self._safe_repo(repo_path)
            return self._run_git_cmd(target_repo, ["checkout", "-b", branch_name])
        except SandboxViolationError as exc:
            return {"success": False, "error": str(exc)}

    def git_commit_and_push(self, repo_path: str, message: str, branch: str) -> dict[str, Any]:
        """Commit atar ve uzak sunucuya pushlar (Onay gerektirir)."""
        if branch in ["main", "master"]:
            return {"success": False, "error": "main veya master branch'lerine doğrudan push yapılması güvenlik ilkesi gereği engellenmiştir. Feature branch oluşturun."}
            
        try:
            target_repo = self._safe_repo(repo_path)
            
            add_res = self._run_git_cmd(target_repo, ["add", "."])
            if not add_res["success"]:
                return add_res
                
            commit_res = self._run_git_cmd(target_repo, ["commit", "-m", message])
            if not commit_res["success"] and "nothing to commit" not in commit_res["output"]:
                return commit_res
                
            push_res = self._run_git_cmd(target_repo, ["push", "origin", branch])
            return push_res
        except SandboxViolationError as exc:
            return {"success": False, "error": str(exc)}

    def github_create_pull_request(self, repo: str, branch: str, title: str) -> dict[str, Any]:
        """GitHub PR açar (Onay gerektirir)."""
        token = settings.GITHUB_TOKEN
        if not token:
            return {"success": False, "error": "Sistemde GITHUB_TOKEN yapılandırılmamış."}
            
        url = f"https://api.github.com/repos/{repo}/pulls"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        data = {
            "title": title,
            "head": branch,
            "base": "main"  # Varsayılan
        }
        
        try:
            resp = requests.post(url, json=data, headers=headers, timeout=15)
            if resp.status_code == 201:
                return {"success": True, "pr_url": resp.json().get("html_url")}
            else:
                return {"success": False, "error": f"API Hatası: {resp.status_code} - {resp.text}"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}


code_server = CodeServer()
