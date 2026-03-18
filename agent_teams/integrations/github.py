"""GitHub integration - auto commit & push at key milestones."""
from __future__ import annotations

import asyncio
import subprocess
from datetime import datetime
from pathlib import Path


def _run(cmd: str, cwd: str | None = None) -> tuple[int, str]:
    """Run a shell command and return (returncode, output)."""
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout + r.stderr).strip()


def git_is_repo(path: str = ".") -> bool:
    code, _ = _run("git rev-parse --is-inside-work-tree", cwd=path)
    return code == 0


def git_has_changes(path: str = ".") -> bool:
    code, out = _run("git status --porcelain", cwd=path)
    return bool(out.strip())


def git_commit(message: str, path: str = ".", files: list[str] | None = None) -> tuple[bool, str]:
    """Stage files and commit. Returns (success, output)."""
    if files:
        for f in files:
            _run(f'git add "{f}"', cwd=path)
    else:
        _run("git add -A", cwd=path)

    code, out = _run(f'git commit -m "{message}"', cwd=path)
    return code == 0, out


def git_push(path: str = ".", branch: str = "main") -> tuple[bool, str]:
    """Push to remote. Returns (success, output)."""
    code, out = _run(f"git push -u origin {branch}", cwd=path)
    return code == 0, out


def ensure_remote(repo_name: str, path: str = ".", private: bool = False) -> tuple[bool, str]:
    """Ensure a GitHub remote exists, create repo if needed."""
    code, out = _run("git remote get-url origin", cwd=path)
    if code == 0:
        return True, out

    visibility = "--private" if private else "--public"
    code, out = _run(
        f'gh repo create {repo_name} {visibility} --source=. --remote=origin --push',
        cwd=path,
    )
    return code == 0, out


class AutoGit:
    """Manages automatic git operations for agent teams output."""

    def __init__(self, repo_path: str, repo_name: str = "", auto_push: bool = True):
        self.repo_path = repo_path
        self.repo_name = repo_name
        self.auto_push = auto_push
        self._initialized = False

    def init(self) -> str:
        """Ensure git repo and remote are ready. Returns status message."""
        if self._initialized:
            return "already initialized"

        if not git_is_repo(self.repo_path):
            _run("git init && git branch -M main", cwd=self.repo_path)

        if self.repo_name:
            ok, msg = ensure_remote(self.repo_name, self.repo_path, private=True)
            if not ok:
                return f"remote setup failed: {msg}"

        self._initialized = True
        return "ready"

    def checkpoint(self, milestone: str, files: list[str] | None = None) -> str:
        """Commit current state as a milestone, optionally push."""
        if not git_has_changes(self.repo_path):
            return "no changes"

        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        msg = f"[agent-teams] {milestone} ({ts})"

        ok, out = git_commit(msg, self.repo_path, files)
        if not ok:
            return f"commit failed: {out}"

        result = f"committed: {milestone}"

        if self.auto_push:
            ok, out = git_push(self.repo_path)
            if ok:
                result += " + pushed"
            else:
                result += f" (push failed: {out})"

        return result
