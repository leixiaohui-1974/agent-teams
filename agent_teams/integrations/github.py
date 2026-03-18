"""GitHub integration - auto commit & push at key milestones."""
from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path


def _run(cmd: str, cwd: str | None = None) -> tuple[int, str]:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout + r.stderr).strip()


def find_git_root(start: str = ".") -> str | None:
    """Walk up from start to find the nearest .git repo root. Returns None if not in a repo."""
    code, out = _run("git rev-parse --show-toplevel", cwd=start)
    if code == 0 and out:
        return out.strip()
    return None


def git_has_remote(path: str) -> bool:
    code, out = _run("git remote get-url origin", cwd=path)
    return code == 0


def git_current_branch(path: str) -> str:
    code, out = _run("git branch --show-current", cwd=path)
    return out.strip() if code == 0 else "main"


def git_has_changes(path: str) -> bool:
    code, out = _run("git status --porcelain", cwd=path)
    return bool(out.strip())


def git_commit(message: str, path: str, files: list[str] | None = None) -> tuple[bool, str]:
    if files:
        for f in files:
            _run(f'git add "{f}"', cwd=path)
    else:
        _run("git add -A", cwd=path)
    code, out = _run(f'git commit -m "{message}"', cwd=path)
    return code == 0, out


def git_push(path: str) -> tuple[bool, str]:
    branch = git_current_branch(path)
    code, out = _run(f"git push -u origin {branch}", cwd=path)
    return code == 0, out


def ensure_remote(repo_name: str, path: str, private: bool = True) -> tuple[bool, str]:
    if git_has_remote(path):
        code, url = _run("git remote get-url origin", cwd=path)
        return True, url

    visibility = "--private" if private else "--public"
    code, out = _run(
        f'gh repo create {repo_name} {visibility} --source=. --remote=origin --push',
        cwd=path,
    )
    return code == 0, out


class AutoGit:
    """Git operations scoped to the user's current project directory.

    Resolution order:
    1. Explicit repo_path if given
    2. Detect git root from cwd
    3. Use cwd itself (init new repo if needed)
    """

    def __init__(
        self,
        cwd: str | None = None,
        repo_name: str | None = None,
        auto_push: bool = True,
        auto_init: bool = False,
    ):
        self.cwd = str(Path(cwd).resolve()) if cwd else str(Path.cwd())
        self.repo_name = repo_name
        self.auto_push = auto_push
        self.auto_init = auto_init
        self.repo_path: str | None = None
        self._ready = False

    def init(self) -> str:
        """Detect or initialize git repo. Returns status message."""
        if self._ready:
            return f"ready ({self.repo_path})"

        # 1. Try to find existing git root from cwd
        root = find_git_root(self.cwd)

        if root:
            self.repo_path = root
            self._ready = True
            has_remote = git_has_remote(root)
            return f"found repo: {root}" + (" (has remote)" if has_remote else " (local only)")

        # 2. No git repo found
        if not self.auto_init:
            return f"no git repo at {self.cwd} (use --git-init to create one)"

        # 3. Auto-init new repo at cwd
        _run("git init && git branch -M main", cwd=self.cwd)
        self.repo_path = self.cwd

        # Create GitHub remote if repo_name provided
        if self.repo_name:
            ok, msg = ensure_remote(self.repo_name, self.cwd, private=True)
            if not ok:
                self._ready = True
                return f"repo initialized at {self.cwd} (remote failed: {msg})"

        self._ready = True
        return f"new repo initialized: {self.cwd}"

    def checkpoint(self, milestone: str, files: list[str] | None = None) -> str:
        """Commit current state as a milestone, optionally push."""
        if not self._ready or not self.repo_path:
            return "git not initialized"

        if not git_has_changes(self.repo_path):
            return "no changes to commit"

        ts = datetime.now().strftime("%m-%d %H:%M")
        msg = f"[ai] {milestone} ({ts})"

        ok, out = git_commit(msg, self.repo_path, files)
        if not ok:
            return f"commit failed: {out}"

        result = f"committed: {milestone}"

        if self.auto_push and git_has_remote(self.repo_path):
            ok, out = git_push(self.repo_path)
            result += " + pushed" if ok else f" (push failed: {out})"

        return result

    @property
    def status(self) -> str:
        if not self.repo_path:
            return "not initialized"
        branch = git_current_branch(self.repo_path)
        has_remote = git_has_remote(self.repo_path)
        changes = git_has_changes(self.repo_path)
        return (
            f"repo={self.repo_path} branch={branch} "
            f"remote={'yes' if has_remote else 'no'} "
            f"changes={'yes' if changes else 'clean'}"
        )
