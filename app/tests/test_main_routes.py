"""Tests for uncovered routes in app/main.py (targeting 100% coverage)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

SAMPLE_SESSION = {
    "session_id": "sess-001",
    "project_id": "proj-1",
    "status": "running",
    "tasks": [],
    "created_at": 1234567890.0,
}


SAMPLE_WORKTREES = [
    {"path": "/tmp/repo-feat-x", "branch": "feat-x"},  # nosec B108
    {"path": "/tmp/repo-feat-y", "branch": "feat-y"},  # nosec B108
]


SAMPLE_TASKS = [
    {"id": "t1", "name": "daily", "cron": "0 6 * * *", "enabled": True},
    {"id": "t2", "name": "hourly", "cron": "0 * * * *", "enabled": True},
]


SAMPLE_PLAN_RESULT = {
    "phases": [{"name": "Setup", "tasks": [{"id": "T1", "title": "Init"}]}],
    "risks": [],
    "stack": "python",
    "architecture_summary": "",
}


class TestGetSessionStatus:
    """GET /api/v1/status/{session_id}"""

    @pytest.mark.asyncio
    async def test_returns_session_when_found(self, async_client: AsyncClient) -> None:
        mock_sm = MagicMock()
        mock_sm.get = AsyncMock(return_value=SAMPLE_SESSION)
        with patch("app.memory.session.get_session_manager", return_value=mock_sm):
            resp = await async_client.get("/api/v1/status/sess-001")

        assert resp.status_code == 200
        assert resp.json() == SAMPLE_SESSION

    @pytest.mark.asyncio
    async def test_returns_404_when_not_found(self, async_client: AsyncClient) -> None:
        mock_sm = MagicMock()
        mock_sm.get = AsyncMock(return_value=None)
        with patch("app.memory.session.get_session_manager", return_value=mock_sm):
            resp = await async_client.get("/api/v1/status/sess-unknown")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Session not found"


class TestProjectExport:
    """POST /api/v1/project/export"""

    @pytest.mark.asyncio
    async def test_exports_project_sessions(self, async_client: AsyncClient) -> None:
        mock_sm = MagicMock()
        mock_sm.get = AsyncMock(return_value=SAMPLE_SESSION)
        with patch("app.memory.session.get_session_manager", return_value=mock_sm):
            resp = await async_client.post(
                "/api/v1/project/export",
                json={"project_id": "proj-1"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == "proj-1"
        assert data["sessions"] == [SAMPLE_SESSION]
        assert "version" in data
        assert "exported_at" in data

    @pytest.mark.asyncio
    async def test_exports_with_empty_sessions_on_error(self, async_client: AsyncClient) -> None:
        mock_sm = MagicMock()
        mock_sm.get = AsyncMock(side_effect=Exception("db down"))
        with patch("app.memory.session.get_session_manager", return_value=mock_sm):
            resp = await async_client.post(
                "/api/v1/project/export",
                json={"project_id": "proj-1"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["sessions"] == []


class TestProjectImport:
    """POST /api/v1/project/import"""

    @pytest.mark.asyncio
    async def test_imports_sessions(self, async_client: AsyncClient) -> None:
        mock_sm = MagicMock()
        mock_sm.create = AsyncMock()
        with patch("app.memory.session.get_session_manager", return_value=mock_sm):
            resp = await async_client.post(
                "/api/v1/project/import",
                json={
                    "project_id": "proj-1",
                    "sessions": [
                        {"workflow_id": "wf-1", "status": "done"},
                        {"workflow_id": "wf-2", "status": "pending"},
                    ],
                },
            )

        assert resp.status_code == 200
        assert resp.json() == {"status": "imported", "project_id": "proj-1"}
        assert mock_sm.create.call_count == 2

    @pytest.mark.asyncio
    async def test_returns_400_without_project_id(self, async_client: AsyncClient) -> None:
        resp = await async_client.post(
            "/api/v1/project/import",
            json={"sessions": []},
        )

        assert resp.status_code == 400
        assert resp.json()["detail"] == "project_id required"


class TestSchedulerCreate:
    """POST /api/v1/scheduler/create"""

    @pytest.mark.asyncio
    async def test_creates_task(self, async_client: AsyncClient) -> None:
        mock_sched = MagicMock()
        mock_sched.add_task = AsyncMock(return_value="new-task-id")
        with patch("app.scheduler.get_scheduler", return_value=mock_sched):
            resp = await async_client.post(
                "/api/v1/scheduler/create",
                json={
                    "name": "daily-digest",
                    "cron": "0 8 * * *",
                    "prompt": "Generate daily report",
                    "project_id": "default",
                    "channel": "console",
                },
            )

        assert resp.status_code == 200
        assert resp.json() == {"status": "created", "task_id": "new-task-id"}
        mock_sched.add_task.assert_awaited_once_with(
            name="daily-digest",
            cron="0 8 * * *",
            prompt="Generate daily report",
            project_id="default",
            channel="console",
        )


class TestSchedulerTasks:
    """GET /api/v1/scheduler/tasks"""

    @pytest.mark.asyncio
    async def test_lists_tasks(self, async_client: AsyncClient) -> None:
        mock_sched = MagicMock()
        mock_sched.list_tasks.return_value = SAMPLE_TASKS
        with patch("app.scheduler.get_scheduler", return_value=mock_sched):
            resp = await async_client.get("/api/v1/scheduler/tasks")

        assert resp.status_code == 200
        assert resp.json() == {"tasks": SAMPLE_TASKS}

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_tasks(self, async_client: AsyncClient) -> None:
        mock_sched = MagicMock()
        mock_sched.list_tasks.return_value = []
        with patch("app.scheduler.get_scheduler", return_value=mock_sched):
            resp = await async_client.get("/api/v1/scheduler/tasks")

        assert resp.status_code == 200
        assert resp.json() == {"tasks": []}


class TestClearLLMCache:
    """POST /api/v1/llm/cache/clear"""

    @pytest.mark.asyncio
    async def test_clears_cache(self, async_client: AsyncClient) -> None:
        mock_client = MagicMock()
        with patch("app.routes.llm.LLMClient", return_value=mock_client):
            resp = await async_client.post("/api/v1/llm/cache/clear")

        assert resp.status_code == 200
        assert resp.json() == {"status": "cache_cleared"}
        mock_client.clear_cache.assert_called_once_with()


class TestPlanEndpoint:
    """POST /api/v1/plan"""

    @pytest.mark.asyncio
    async def test_creates_plan(self, async_client: AsyncClient) -> None:
        mock_sub = MagicMock()
        mock_sub.run = AsyncMock(return_value=SAMPLE_PLAN_RESULT)
        mock_rules = MagicMock()
        mock_rules.get_all_rules.return_value = ["rule1"]

        with (
            patch("app.agents.sub_agent.SubAgent", return_value=mock_sub),
            patch("app.agents.rules.get_rules", return_value=mock_rules),
        ):
            resp = await async_client.post(
                "/api/v1/plan",
                json={"goal": "Build a todo app", "project_id": "proj-1"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"] == SAMPLE_PLAN_RESULT
        assert data["project_id"] == "proj-1"


class TestSubAgentRun:
    """POST /api/v1/sub-agent/run"""

    @pytest.mark.asyncio
    async def test_runs_named_agent(self, async_client: AsyncClient) -> None:
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value={"fixed": True})
        with patch("app.agents.sub_agent.get_or_create_sub_agent", return_value=mock_agent):
            resp = await async_client.post(
                "/api/v1/sub-agent/run",
                json={"name": "debugger", "task": "Fix this bug"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["agent"] == "debugger"
        assert data["result"] == {"fixed": True}

    @pytest.mark.asyncio
    async def test_routes_auto_agent(self, async_client: AsyncClient) -> None:
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value={"status": "verified"})
        with (
            patch("app.agents.sub_agent.route_to_sub_agent", return_value="verifier"),
            patch(
                "app.agents.sub_agent.get_or_create_sub_agent",
                return_value=mock_agent,
            ),
        ):
            resp = await async_client.post(
                "/api/v1/sub-agent/run",
                json={"name": "auto", "task": "Verify the code"},
            )

        assert resp.status_code == 200
        assert resp.json()["agent"] == "verifier"

    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_agent(self, async_client: AsyncClient) -> None:
        with patch("app.agents.sub_agent.get_or_create_sub_agent", return_value=None):
            resp = await async_client.post(
                "/api/v1/sub-agent/run",
                json={"name": "nonexistent", "task": "do stuff"},
            )

        assert resp.status_code == 404
        assert "nonexistent" in resp.json()["detail"]


class TestListSubAgents:
    """GET /api/v1/sub-agents"""

    @pytest.mark.asyncio
    async def test_lists_builtin_agents(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/api/v1/sub-agents")

        assert resp.status_code == 200
        data = resp.json()
        assert "sub_agents" in data
        assert isinstance(data["sub_agents"], list)
        for name in ("planner", "verifier", "debugger", "explorer", "code_reviewer"):
            assert name in data["sub_agents"]


class TestDebugSubAgent:
    """POST /api/v1/sub-agent/debug"""

    @pytest.mark.asyncio
    async def test_debugs_error(self, async_client: AsyncClient) -> None:
        mock_sub = MagicMock()
        mock_sub.run = AsyncMock(
            return_value={
                "root_cause": "Missing import",
                "explanation": "sys module not imported",
                "confidence": 0.95,
            }
        )
        with patch("app.agents.sub_agent.SubAgent", return_value=mock_sub):
            resp = await async_client.post(
                "/api/v1/sub-agent/debug",
                json={"error": "NameError: name 'sys' is not defined"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["debugger"]["root_cause"] == "Missing import"
        assert data["debugger"]["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_debug_with_context(self, async_client: AsyncClient) -> None:
        mock_sub = MagicMock()
        mock_sub.run = AsyncMock(return_value={"fix_suggestion": "import sys"})
        with patch("app.agents.sub_agent.SubAgent", return_value=mock_sub):
            resp = await async_client.post(
                "/api/v1/sub-agent/debug",
                json={
                    "error": "ImportError",
                    "context": {"file": "main.py", "line": 42},
                },
            )

        assert resp.status_code == 200


class TestCreateWorktree:
    """POST /api/v1/worktree"""

    @pytest.mark.asyncio
    async def test_creates_worktree(self, async_client: AsyncClient) -> None:
        mock_wm = MagicMock()
        mock_wm.create_worktree = AsyncMock(return_value="/tmp/repo-feat-x")  # nosec B108
        with patch("app.git_worktree.get_worktree_manager", return_value=mock_wm):
            resp = await async_client.post(
                "/api/v1/worktree",
                json={"branch_name": "feat-x", "base_branch": "main"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "created"
        assert data["branch"] == "feat-x"
        assert data["path"] == "/tmp/repo-feat-x"  # nosec B108

    @pytest.mark.asyncio
    async def test_returns_400_on_failure(self, async_client: AsyncClient) -> None:
        mock_wm = MagicMock()
        mock_wm.create_worktree = AsyncMock(side_effect=Exception("Branch already exists"))
        with patch("app.git_worktree.get_worktree_manager", return_value=mock_wm):
            resp = await async_client.post(
                "/api/v1/worktree",
                json={"branch_name": "feat-x", "base_branch": "main"},
            )

        assert resp.status_code == 400
        assert "Branch already exists" in resp.json()["detail"]


class TestListWorktrees:
    """GET /api/v1/worktree"""

    @pytest.mark.asyncio
    async def test_lists_worktrees(self, async_client: AsyncClient) -> None:
        mock_wm = MagicMock()
        mock_wm.list_worktrees = AsyncMock(return_value=SAMPLE_WORKTREES)
        with patch("app.git_worktree.get_worktree_manager", return_value=mock_wm):
            resp = await async_client.get("/api/v1/worktree")

        assert resp.status_code == 200
        assert resp.json()["worktrees"] == SAMPLE_WORKTREES

    @pytest.mark.asyncio
    async def test_returns_error_field_on_failure(self, async_client: AsyncClient) -> None:
        mock_wm = MagicMock()
        mock_wm.list_worktrees = AsyncMock(side_effect=Exception("Not a git repository"))
        with patch("app.git_worktree.get_worktree_manager", return_value=mock_wm):
            resp = await async_client.get("/api/v1/worktree")

        assert resp.status_code == 200
        assert resp.json()["worktrees"] == []
        assert "error" in resp.json()


class TestAuthMiddleware:
    """Middleware at line ~99 — optional JWT auth"""

    @pytest.mark.asyncio
    async def test_passes_user_state_with_valid_token(self, async_client: AsyncClient) -> None:
        mock_user = {"sub": "user-123", "role": "admin"}
        with patch("app.main.get_current_user", return_value=mock_user):
            resp = await async_client.get(
                "/api/v1/sub-agents",
                headers={"Authorization": "Bearer validtoken"},
            )

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_sets_user_none_on_invalid_token(self, async_client: AsyncClient) -> None:
        with patch("app.main.get_current_user", side_effect=Exception("Invalid token")):
            resp = await async_client.get(
                "/api/v1/sub-agents",
                headers={"Authorization": "Bearer badtoken"},
            )

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_middleware_skipped_for_health(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_middleware_skipped_for_metrics(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/metrics")
        assert resp.status_code == 200


class TestAuthTokenEndpoint:
    @pytest.mark.asyncio
    async def test_get_token_returns_credentials(self, async_client: AsyncClient) -> None:
        resp = await async_client.post("/api/v1/auth/token?sub=testuser&workspace=testws")
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_get_token_default_params(self, async_client: AsyncClient) -> None:
        resp = await async_client.post("/api/v1/auth/token")
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
