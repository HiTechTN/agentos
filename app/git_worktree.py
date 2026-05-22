"""Git worktree isolation for parallel agent execution."""

import asyncio
from pathlib import Path
from typing import Any

from app.utils.logging import get_logger

logger = get_logger("git_worktree")


class WorktreeError(Exception):
    pass


class GitWorktreeManager:
    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path).resolve()
        self.logger = get_logger("git_worktree")

    async def _run_git(self, *args: str) -> str:
        cmd = ["git", "-C", str(self.repo_path)] + list(args)
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise WorktreeError(stderr.decode().strip())
        return stdout.decode().strip()

    async def create_worktree(self, branch_name: str, base_branch: str = "main") -> Path:
        worktree_path = self.repo_path.parent / f"{self.repo_path.name}-{branch_name}"
        try:
            await self._run_git("branch", "-D", branch_name)
        except WorktreeError:
            pass
        await self._run_git("checkout", "-b", branch_name, base_branch)
        await self._run_git("push", "origin", branch_name, "--set-upstream")
        await self._run_git("worktree", "add", str(worktree_path), branch_name)
        await self._run_git("checkout", base_branch)
        self.logger.log_action(
            "worktree",
            "create",
            "completed",
            details={"branch": branch_name, "path": str(worktree_path)},
        )
        return worktree_path

    async def remove_worktree(self, branch_name: str):
        worktree_path = self.repo_path.parent / f"{self.repo_path.name}-{branch_name}"
        try:
            await self._run_git("worktree", "remove", str(worktree_path), "--force")
        except WorktreeError:
            pass
        try:
            await self._run_git("branch", "-D", branch_name)
        except WorktreeError:
            pass
        self.logger.log_action("worktree", "remove", "completed", details={"branch": branch_name})

    async def rebase_to_main(self, branch_name: str):
        await self._run_git("checkout", branch_name)
        await self._run_git("rebase", "main")
        await self._run_git("checkout", "main")
        self.logger.log_action("worktree", "rebase", "completed", details={"branch": branch_name})

    async def list_worktrees(self) -> list[dict[str, str]]:
        output = await self._run_git("worktree", "list")
        worktrees = []
        for line in output.strip().split("\n"):
            parts = line.split()
            if len(parts) >= 3:
                worktrees.append({"path": parts[0], "branch": parts[2].strip("[]")})
        return worktrees

    async def get_status(self, worktree_path: str) -> dict[str, Any]:
        try:
            status = await self._run_git("-C", worktree_path, "status", "--porcelain")
            branch = await self._run_git("-C", worktree_path, "rev-parse", "--abbrev-ref", "HEAD")
            return {
                "branch": branch,
                "has_changes": bool(status.strip()),
                "path": worktree_path,
            }
        except WorktreeError as e:
            return {"error": str(e)}


_git_worktree_manager: GitWorktreeManager | None = None


def get_worktree_manager(repo_path: str = ".") -> GitWorktreeManager:
    global _git_worktree_manager
    if _git_worktree_manager is None:
        _git_worktree_manager = GitWorktreeManager(repo_path)
    return _git_worktree_manager
