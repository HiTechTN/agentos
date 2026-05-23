from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.git_worktree import GitWorktreeManager, WorktreeError, get_worktree_manager


class TestWorktreeError:
    def test_is_exception(self) -> None:
        assert issubclass(WorktreeError, Exception)


class TestGitWorktreeManager:
    def test_init_default_path(self) -> None:
        mgr = GitWorktreeManager()
        assert mgr.repo_path == Path.cwd().resolve()

    def test_init_custom_path(self) -> None:
        mgr = GitWorktreeManager("/tmp")
        assert mgr.repo_path == Path("/tmp").resolve()

    @pytest.mark.asyncio
    async def test_run_git_success(self) -> None:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"hello", b""))
        mgr = GitWorktreeManager()
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
            result = await mgr._run_git("status")
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_run_git_failure(self) -> None:
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"fatal: not a git repository"))
        mgr = GitWorktreeManager()
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
            with pytest.raises(WorktreeError, match="fatal: not a git repository"):
                await mgr._run_git("status")

    @pytest.mark.asyncio
    async def test_create_worktree(self) -> None:
        mgr = GitWorktreeManager("/tmp/repo")
        mgr._run_git = AsyncMock()  # type: ignore[method-assign]
        result = await mgr.create_worktree("feature-x", "main")
        expected_path = Path("/tmp/repo-feature-x")
        assert result == expected_path
        mgr._run_git.assert_any_call("branch", "-D", "feature-x")
        mgr._run_git.assert_any_call("checkout", "-b", "feature-x", "main")
        mgr._run_git.assert_any_call("push", "origin", "feature-x", "--set-upstream")
        mgr._run_git.assert_any_call("worktree", "add", str(expected_path), "feature-x")
        mgr._run_git.assert_any_call("checkout", "main")

    @pytest.mark.asyncio
    async def test_create_worktree_branch_delete_fails(self) -> None:
        mgr = GitWorktreeManager("/tmp/repo")
        mgr._run_git = AsyncMock(side_effect=[WorktreeError("no branch"), None, None, None, None])  # type: ignore[method-assign]
        result = await mgr.create_worktree("feature-x", "main")
        assert result == Path("/tmp/repo-feature-x")
        assert mgr._run_git.call_count == 5

    @pytest.mark.asyncio
    async def test_remove_worktree(self) -> None:
        mgr = GitWorktreeManager("/tmp/repo")
        mgr._run_git = AsyncMock()  # type: ignore[method-assign]
        await mgr.remove_worktree("feature-x")
        mgr._run_git.assert_any_call("worktree", "remove", "/tmp/repo-feature-x", "--force")
        mgr._run_git.assert_any_call("branch", "-D", "feature-x")

    @pytest.mark.asyncio
    async def test_remove_worktree_removal_fails(self) -> None:
        mgr = GitWorktreeManager("/tmp/repo")
        mgr._run_git = AsyncMock(side_effect=[WorktreeError("no worktree"), None])  # type: ignore[method-assign]
        await mgr.remove_worktree("feature-x")
        assert mgr._run_git.call_count == 2

    @pytest.mark.asyncio
    async def test_remove_worktree_both_fail(self) -> None:
        mgr = GitWorktreeManager("/tmp/repo")
        mgr._run_git = AsyncMock(  # type: ignore[method-assign]
            side_effect=[WorktreeError("no worktree"), WorktreeError("no branch")]
        )
        await mgr.remove_worktree("feature-x")
        assert mgr._run_git.call_count == 2

    @pytest.mark.asyncio
    async def test_rebase_to_main(self) -> None:
        mgr = GitWorktreeManager()
        mgr._run_git = AsyncMock()  # type: ignore[method-assign]
        await mgr.rebase_to_main("feature-x")
        mgr._run_git.assert_any_call("checkout", "feature-x")
        mgr._run_git.assert_any_call("rebase", "main")
        mgr._run_git.assert_any_call("checkout", "main")

    @pytest.mark.asyncio
    async def test_list_worktrees(self) -> None:
        mgr = GitWorktreeManager()
        mgr._run_git = AsyncMock(  # type: ignore[method-assign]
            return_value="/home/user/project  abc123 [main]\n/tmp/repo-feature-x   def456 [feature-x]"  # noqa: E501
        )
        result = await mgr.list_worktrees()
        assert result == [
            {"path": "/home/user/project", "branch": "main"},
            {"path": "/tmp/repo-feature-x", "branch": "feature-x"},
        ]

    @pytest.mark.asyncio
    async def test_list_worktrees_empty(self) -> None:
        mgr = GitWorktreeManager()
        mgr._run_git = AsyncMock(return_value="")  # type: ignore[method-assign]
        result = await mgr.list_worktrees()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_status_with_changes(self) -> None:
        mgr = GitWorktreeManager()
        mgr._run_git = AsyncMock(side_effect=["M  file.txt\n", "feature-x"])  # type: ignore[method-assign]
        result = await mgr.get_status("/tmp/repo-feature-x")
        assert result == {
            "branch": "feature-x",
            "has_changes": True,
            "path": "/tmp/repo-feature-x",
        }

    @pytest.mark.asyncio
    async def test_get_status_without_changes(self) -> None:
        mgr = GitWorktreeManager()
        mgr._run_git = AsyncMock(side_effect=["", "main"])  # type: ignore[method-assign]
        result = await mgr.get_status("/tmp/repo-feature-x")
        assert result == {
            "branch": "main",
            "has_changes": False,
            "path": "/tmp/repo-feature-x",
        }

    @pytest.mark.asyncio
    async def test_get_status_error(self) -> None:
        mgr = GitWorktreeManager()
        mgr._run_git = AsyncMock(side_effect=WorktreeError("fatal: not a git repository"))  # type: ignore[method-assign]
        result = await mgr.get_status("/tmp/repo-feature-x")
        assert result == {"error": "fatal: not a git repository"}

    @pytest.mark.asyncio
    async def test_get_singleton_default(self) -> None:
        import app.git_worktree as gw_module

        with patch.object(gw_module, "_git_worktree_manager", None):
            s1 = get_worktree_manager()
            s2 = get_worktree_manager()
            assert s1 is s2
            assert s1.repo_path == Path.cwd().resolve()

    @pytest.mark.asyncio
    async def test_get_singleton_custom_path(self) -> None:
        import app.git_worktree as gw_module

        with patch.object(gw_module, "_git_worktree_manager", None):
            s1 = get_worktree_manager("/tmp/custom")
            s2 = get_worktree_manager()
            assert s1 is s2
            assert s1.repo_path == Path("/tmp/custom").resolve()
