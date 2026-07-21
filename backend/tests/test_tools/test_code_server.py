import os
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from mcp_servers.code_server import CodeServer, ALLOWED_IMAGES

# Fixtures
@pytest.fixture
def sandbox_dir(tmp_path):
    # Dummy sandbox dir
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    
    # Dummy repo
    repo = sandbox / "my_repo"
    repo.mkdir()
    
    # Set allowed repos
    with patch("config.settings.ALLOWED_REPOS", f"{repo}"):
        yield sandbox

@pytest.fixture
def code_server(sandbox_dir):
    return CodeServer(sandbox_root=sandbox_dir)

@pytest.fixture
def dummy_file(sandbox_dir):
    f = sandbox_dir / "test.py"
    f.write_text("print('hello')")
    return f

# ── Docker Sandbox Mock Testleri ─────────────────────────────────────────────

class TestDockerSandbox:
    @patch("mcp_servers.code_server.subprocess.run")
    def test_code_run_builds_correct_docker_cmd(self, mock_run, code_server, dummy_file):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "hello\n"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        result = code_server.code_run(str(dummy_file), "python")
        
        assert result["success"] is True
        assert result["stdout"] == "hello\n"
        
        # subprocess.run nasıl çağrıldı?
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        
        cmd = args[0]
        assert type(cmd) == list
        assert cmd[0:3] == ["docker", "run", "--rm"]
        assert "--network" in cmd
        assert "none" in cmd
        assert "--memory=256m" in cmd
        assert "--cap-drop=ALL" in cmd
        assert "--security-opt=no-new-privileges" in cmd
        assert "--read-only" in cmd
        
        # volume mount
        host_dir = str(dummy_file.parent)
        assert "-v" in cmd
        assert f"{host_dir}:/workspace:rw" in cmd
        
        # image
        assert ALLOWED_IMAGES["python"] in cmd
        
        # command
        assert cmd[-2:] == ["python", "/workspace/test.py"]
        
        assert kwargs["shell"] is False

    def test_code_run_unsupported_language(self, code_server, dummy_file):
        result = code_server.code_run(str(dummy_file), "java")
        assert result["success"] is False
        assert "Desteklenmeyen dil" in result["error"]

    def test_code_run_sandbox_violation(self, code_server):
        result = code_server.code_run("../../etc/passwd", "python")
        assert result["success"] is False
        assert "Sandbox dışına çıkamaz" in result["error"]

    @patch("mcp_servers.code_server.subprocess.run")
    def test_code_run_truncates_output(self, mock_run, code_server, dummy_file):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "A" * 5000
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        result = code_server.code_run(str(dummy_file), "python")
        assert len(result["stdout"]) < 5000
        assert "[çıktı kesildi]" in result["stdout"]


# ── Git Tool Testleri ────────────────────────────────────────────────────────

class TestGitTools:
    @patch("mcp_servers.code_server.subprocess.run")
    def test_git_status_allowed_repo(self, mock_run, code_server, sandbox_dir):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = " M README.md"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        repo_path = sandbox_dir / "my_repo"
        result = code_server.git_status(str(repo_path))
        
        assert result["success"] is True
        assert result["output"] == " M README.md"
        
        args, kwargs = mock_run.call_args
        assert args[0] == ["git", "status", "-s"]
        assert kwargs["cwd"] == str(repo_path.resolve())

    def test_git_repo_not_in_allowed(self, code_server, sandbox_dir):
        # Create a repo inside sandbox but NOT in ALLOWED_REPOS
        unallowed_repo = sandbox_dir / "unallowed"
        unallowed_repo.mkdir()
        
        result = code_server.git_status(str(unallowed_repo))
        assert result["success"] is False
        assert "ALLOWED_REPOS listesinde değil" in result["error"]

    def test_git_commit_and_push_rejects_main(self, code_server, sandbox_dir):
        repo_path = sandbox_dir / "my_repo"
        
        res1 = code_server.git_commit_and_push(str(repo_path), "msg", "main")
        assert res1["success"] is False
        assert "doğrudan push yapılması güvenlik ilkesi gereği engellenmiştir" in res1["error"]
        
        res2 = code_server.git_commit_and_push(str(repo_path), "msg", "master")
        assert res2["success"] is False
        assert "doğrudan push yapılması güvenlik ilkesi gereği engellenmiştir" in res2["error"]

# ── GitHub PR Testleri ───────────────────────────────────────────────────────

class TestGithubPR:
    @patch("mcp_servers.code_server.requests.post")
    def test_github_pr_success(self, mock_post, code_server):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"html_url": "https://github.com/repo/pulls/1"}
        mock_post.return_value = mock_resp
        
        with patch("config.settings.GITHUB_TOKEN", "fake_token"):
            result = code_server.github_create_pull_request("owner/repo", "feat/test", "PR Title")
            
            assert result["success"] is True
            assert result["pr_url"] == "https://github.com/repo/pulls/1"
            
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert args[0] == "https://api.github.com/repos/owner/repo/pulls"
            assert kwargs["headers"]["Authorization"] == "token fake_token"
            assert kwargs["json"]["head"] == "feat/test"
            assert kwargs["json"]["base"] == "main"

    def test_github_pr_missing_token(self, code_server):
        with patch("config.settings.GITHUB_TOKEN", ""):
            result = code_server.github_create_pull_request("owner/repo", "feat/test", "PR Title")
            assert result["success"] is False
            assert "yapılandırılmamış" in result["error"]

# ── Gerçek Docker Smoke Testi ────────────────────────────────────────────────

def has_docker():
    try:
        return subprocess.run(["docker", "info"], capture_output=True).returncode == 0
    except FileNotFoundError:
        return False

@pytest.mark.skipif(
    not has_docker(),
    reason="Docker is not running or not installed"
)
def test_smoke_docker_python(code_server, tmp_path):
    """
    Gerçek Docker daemon kullanarak 1+1 işlemini test eder.
    """
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir(exist_ok=True)
    code_server.sandbox_root = sandbox
    
    script_file = sandbox / "smoke.py"
    script_file.write_text("print(1 + 1)")
    
    # We must ensure the python:3.10-slim image is present, otherwise docker run might fail or try to download
    # In CI, we usually docker pull first. Here we just run and see.
    result = code_server.code_run(str(script_file), "python")
    
    assert result["success"] is True, f"Docker run failed: {result}"
    assert "2\n" in result["stdout"]
