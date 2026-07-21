"""integrations/github_tools.py — GitHub entegrasyonu stub. Faz 3'te aktif olacak."""
_STUB_MSG = "GitHub entegrasyonu Faz 3'te implemente edilecek."

def git_status(repo_path: str) -> dict: raise NotImplementedError(_STUB_MSG)
def git_diff_preview(repo_path: str) -> dict: raise NotImplementedError(_STUB_MSG)
def git_commit_and_push(repo_path: str, message: str, branch: str) -> dict: raise NotImplementedError(_STUB_MSG)
def github_create_pull_request(repo: str, branch: str, title: str) -> dict: raise NotImplementedError(_STUB_MSG)
