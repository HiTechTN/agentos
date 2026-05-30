"""Cover remaining uncovered routes in app/main.py for 100% coverage."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

_SPANS = [
    {"name": "s1", "trace_id": "t1", "duration_ms": 100},
    {"name": "s2", "trace_id": "t2", "duration_ms": 200},
]


class TestRunWorkflow:
    @pytest.mark.asyncio
    async def test_runs_workflow(self, async_client: AsyncClient) -> None:
        mock_orch = MagicMock()
        mock_orch.run = AsyncMock(return_value={"result": "done"})
        with patch("app.routes.workflow.get_orchestrator", return_value=mock_orch):
            resp = await async_client.post(
                "/api/v1/run", json={"prompt": "test", "project_id": "p1"}
            )
        assert resp.status_code == 200
        assert resp.json() == {"result": "done"}


class TestHITLEndpoints:
    @pytest.mark.asyncio
    async def test_approve_success(self, async_client: AsyncClient) -> None:
        gw, notif = MagicMock(), AsyncMock()
        gw.approve.return_value = {"ok": True}
        with (
            patch("app.routes.workflow.get_hitl_gateway", return_value=gw),
            patch("app.utils.notifications.get_notifications", return_value=notif),
        ):
            resp = await async_client.post("/api/v1/hitl/approve", json={"approval_id": "a1"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "approved", "details": {"ok": True}}

    @pytest.mark.asyncio
    async def test_approve_not_found(self, async_client: AsyncClient) -> None:
        gw = MagicMock()
        gw.approve.side_effect = ValueError("not found")
        with patch("app.routes.workflow.get_hitl_gateway", return_value=gw):
            resp = await async_client.post("/api/v1/hitl/approve", json={"approval_id": "bad"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_reject_success(self, async_client: AsyncClient) -> None:
        gw = MagicMock()
        gw.reject.return_value = {"ok": True}
        with patch("app.routes.workflow.get_hitl_gateway", return_value=gw):
            resp = await async_client.post(
                "/api/v1/hitl/reject", json={"approval_id": "a1", "reason": "no"}
            )
        assert resp.status_code == 200
        assert resp.json() == {"status": "rejected", "details": {"ok": True}}

    @pytest.mark.asyncio
    async def test_reject_not_found(self, async_client: AsyncClient) -> None:
        gw = MagicMock()
        gw.reject.side_effect = ValueError("not found")
        with patch("app.routes.workflow.get_hitl_gateway", return_value=gw):
            resp = await async_client.post("/api/v1/hitl/reject", json={"approval_id": "bad"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_pending(self, async_client: AsyncClient) -> None:
        gw = MagicMock()
        gw.get_pending.return_value = [{"id": "a1"}]
        with patch("app.routes.workflow.get_hitl_gateway", return_value=gw):
            resp = await async_client.get("/api/v1/hitl/pending")
        assert resp.status_code == 200
        assert resp.json() == {"pending": [{"id": "a1"}]}


class TestLogsEndpoint:
    @pytest.mark.asyncio
    async def test_returns_logs(self, async_client: AsyncClient) -> None:
        tel = MagicMock()
        tel.get_spans.return_value = _SPANS
        with patch("app.routes.workflow.get_telemetry", return_value=tel):
            resp = await async_client.get("/api/v1/logs")
        assert resp.status_code == 200 and resp.json() == {"logs": _SPANS}

    @pytest.mark.asyncio
    async def test_with_trace_id(self, async_client: AsyncClient) -> None:
        tel = MagicMock()
        tel.get_spans.return_value = [_SPANS[0]]
        with patch("app.routes.workflow.get_telemetry", return_value=tel):
            resp = await async_client.get("/api/v1/logs?trace_id=t1")
        assert resp.status_code == 200 and len(resp.json()["logs"]) == 1


class TestWorkspaceEndpoints:
    @pytest.mark.asyncio
    async def test_list(self, async_client: AsyncClient) -> None:
        wm = MagicMock()
        wm.list_workspaces.return_value = [{"id": "w1"}]
        with patch("app.memory.workspace.get_workspace_manager", return_value=wm):
            resp = await async_client.get("/api/v1/workspaces")
        assert resp.status_code == 200
        assert resp.json() == {"workspaces": [{"id": "w1"}]}

    @pytest.mark.asyncio
    async def test_create(self, async_client: AsyncClient) -> None:
        wm = MagicMock()
        with patch("app.memory.workspace.get_workspace_manager", return_value=wm):
            resp = await async_client.post("/api/v1/workspaces", json={"workspace_id": "w-new"})
        assert resp.status_code == 200
        wm.create_workspace.assert_called_once_with("w-new")

    @pytest.mark.asyncio
    async def test_create_generates_id(self, async_client: AsyncClient) -> None:
        wm = MagicMock()
        with patch("app.memory.workspace.get_workspace_manager", return_value=wm):
            resp = await async_client.post("/api/v1/workspaces", json={})
        assert resp.status_code == 200
        assert len(resp.json()["workspace_id"]) == 8


class TestVerifyEndpoint:
    @pytest.mark.asyncio
    async def test_verifies(self, async_client: AsyncClient) -> None:
        sub = MagicMock()
        sub.run = AsyncMock(return_value={"verified": True})
        with patch("app.agents.sub_agent.SubAgent", return_value=sub):
            resp = await async_client.post("/api/v1/verify", json={"task": "verify code"})
        assert resp.status_code == 200
        assert resp.json() == {"verification": {"verified": True}}


class TestKanbanEndpoints:
    @pytest.mark.asyncio
    async def test_create_card(self, async_client: AsyncClient) -> None:
        board = MagicMock()
        card = MagicMock()
        card.to_dict.return_value = {"id": "c1", "title": "Task", "column": "backlog"}
        board.add_card.return_value = card
        with patch("app.kanban.get_kanban_board", return_value=board):
            resp = await async_client.post("/api/v1/kanban/p1/cards", json={"title": "Task"})
        assert resp.status_code == 200
        assert resp.json() == {"card": {"id": "c1", "title": "Task", "column": "backlog"}}

    @pytest.mark.asyncio
    async def test_get_board(self, async_client: AsyncClient) -> None:
        board = MagicMock()
        board.get_all.return_value = {"backlog": []}
        with patch("app.kanban.get_kanban_board", return_value=board):
            resp = await async_client.get("/api/v1/kanban/p1")
        assert resp.status_code == 200
        assert resp.json() == {"columns": {"backlog": []}}

    @pytest.mark.asyncio
    async def test_move_card(self, async_client: AsyncClient) -> None:
        board = MagicMock()
        board.move_card.return_value = True
        with patch("app.kanban.get_kanban_board", return_value=board):
            resp = await async_client.put(
                "/api/v1/kanban/p1/move", json={"card_id": "c1", "column": "done"}
            )
        assert resp.status_code == 200 and resp.json() == {"status": "moved"}

    @pytest.mark.asyncio
    async def test_move_card_not_found(self, async_client: AsyncClient) -> None:
        board = MagicMock()
        board.move_card.return_value = False
        with patch("app.kanban.get_kanban_board", return_value=board):
            resp = await async_client.put(
                "/api/v1/kanban/p1/move", json={"card_id": "bad", "column": "done"}
            )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_card(self, async_client: AsyncClient) -> None:
        board = MagicMock()
        board.delete_card.return_value = True
        with patch("app.kanban.get_kanban_board", return_value=board):
            resp = await async_client.delete("/api/v1/kanban/p1/cards/c1")
        assert resp.status_code == 200 and resp.json() == {"status": "deleted"}

    @pytest.mark.asyncio
    async def test_delete_card_not_found(self, async_client: AsyncClient) -> None:
        board = MagicMock()
        board.delete_card.return_value = False
        with patch("app.kanban.get_kanban_board", return_value=board):
            resp = await async_client.delete("/api/v1/kanban/p1/cards/bad")
        assert resp.status_code == 404


class TestPulseEndpoints:
    @pytest.mark.asyncio
    async def test_get_snapshot(self, async_client: AsyncClient) -> None:
        board = MagicMock()
        board.get_all.return_value = {"col": []}
        snapshot = MagicMock()
        snapshot.to_dict.return_value = {"agents": {}, "columns": {"col": []}}
        pulse = MagicMock()
        pulse.snapshot = AsyncMock(return_value=snapshot)
        orch = MagicMock()
        orch.agents = ["a1", "a2"]
        with (
            patch("app.kanban.get_kanban_board", return_value=board),
            patch("app.pulse.get_pulse", return_value=pulse),
            patch("app.orchestrator.get_orchestrator", return_value=orch),
        ):
            resp = await async_client.get("/api/v1/pulse/p1")
        assert resp.status_code == 200
        assert resp.json() == {"agents": {}, "columns": {"col": []}}

    @pytest.mark.asyncio
    async def test_get_timeline(self, async_client: AsyncClient) -> None:
        pulse = MagicMock()
        pulse.get_timeline.return_value = [{"event": "moved", "timestamp": 1}]
        with patch("app.pulse.get_pulse", return_value=pulse):
            resp = await async_client.get("/api/v1/pulse/p1/timeline")
        assert resp.status_code == 200
        assert resp.json() == {"timeline": [{"event": "moved", "timestamp": 1}]}


class TestMCPEndpoints:
    @pytest.mark.asyncio
    async def test_register(self, async_client: AsyncClient) -> None:
        registry = MagicMock()
        with patch("app.mcp.server.get_mcp_registry", return_value=registry):
            resp = await async_client.post(
                "/api/v1/mcp/register", json={"name": "svc", "endpoint": "http://s"}
            )
        assert resp.status_code == 200
        assert resp.json() == {"status": "registered", "name": "svc"}

    @pytest.mark.asyncio
    async def test_list_servers(self, async_client: AsyncClient) -> None:
        registry = MagicMock()
        registry.list_servers.return_value = [{"name": "svc"}]
        with patch("app.mcp.server.get_mcp_registry", return_value=registry):
            resp = await async_client.get("/api/v1/mcp/servers")
        assert resp.status_code == 200
        assert resp.json() == {"servers": [{"name": "svc"}]}

    @pytest.mark.asyncio
    async def test_call_tool(self, async_client: AsyncClient) -> None:
        registry = MagicMock()
        registry.call_tool = AsyncMock(return_value={"result": "done"})
        with patch("app.mcp.server.get_mcp_registry", return_value=registry):
            resp = await async_client.post("/api/v1/mcp/my-srv/call/my-tool", json={"x": 1})
        assert resp.status_code == 200
        assert resp.json() == {"result": "done"}


class TestRulesEndpoints:
    @pytest.mark.asyncio
    async def test_get_rules(self, async_client: AsyncClient) -> None:
        rules = MagicMock()
        rules.get_project_rules.return_value = {"py": "hints"}
        rules.get_global_rules.return_value = ["no print"]
        rules.get_plan_rules.return_value = ["max 5"]
        with patch("app.agents.rules.get_rules", return_value=rules):
            resp = await async_client.get("/api/v1/rules")
        assert resp.status_code == 200
        assert resp.json()["project_rules"] == {"py": "hints"}

    @pytest.mark.asyncio
    async def test_init_rules(self, async_client: AsyncClient) -> None:
        rules = MagicMock()
        with patch("app.agents.rules.get_rules", return_value=rules):
            resp = await async_client.post("/api/v1/rules/init")
        assert resp.status_code == 200
        assert resp.json() == {"status": "created", "path": "AGENTS.md"}


class TestWorktreeRemaining:
    @pytest.mark.asyncio
    async def test_rebase_success(self, async_client: AsyncClient) -> None:
        wm = MagicMock()
        wm.rebase_to_main = AsyncMock()
        with patch("app.git_worktree.get_worktree_manager", return_value=wm):
            resp = await async_client.post("/api/v1/worktree/rebase?branch_name=feat-x")
        assert resp.status_code == 200
        assert resp.json() == {"status": "rebased", "branch": "feat-x"}

    @pytest.mark.asyncio
    async def test_rebase_error(self, async_client: AsyncClient) -> None:
        wm = MagicMock()
        wm.rebase_to_main = AsyncMock(side_effect=Exception("conflict"))
        with patch("app.git_worktree.get_worktree_manager", return_value=wm):
            resp = await async_client.post("/api/v1/worktree/rebase?branch_name=feat-x")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_remove_success(self, async_client: AsyncClient) -> None:
        wm = MagicMock()
        wm.remove_worktree = AsyncMock()
        with patch("app.git_worktree.get_worktree_manager", return_value=wm):
            resp = await async_client.delete("/api/v1/worktree/feat-x")
        assert resp.status_code == 200
        assert resp.json() == {"status": "removed", "branch": "feat-x"}

    @pytest.mark.asyncio
    async def test_remove_error(self, async_client: AsyncClient) -> None:
        wm = MagicMock()
        wm.remove_worktree = AsyncMock(side_effect=Exception("not found"))
        with patch("app.git_worktree.get_worktree_manager", return_value=wm):
            resp = await async_client.delete("/api/v1/worktree/bad")
        assert resp.status_code == 400


class TestGuidePage:
    @pytest.mark.asyncio
    async def test_returns_guide(self, async_client: AsyncClient) -> None:
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = "<h1>Guide</h1>"
        with patch("app.main.GUIDE_HTML_PATH", mock_path):
            resp = await async_client.get("/guide")
        assert resp.status_code == 200 and resp.text == "<h1>Guide</h1>"

    @pytest.mark.asyncio
    async def test_not_found(self, async_client: AsyncClient) -> None:
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        with patch("app.main.GUIDE_HTML_PATH", mock_path):
            resp = await async_client.get("/guide")
        assert resp.status_code == 404


class TestDeployPage:
    @pytest.mark.asyncio
    async def test_returns_deploy_page(self, async_client: AsyncClient) -> None:
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = "<h1>Deploy</h1>"
        with patch("app.main.DEPLOY_HTML_PATH", mock_path):
            resp = await async_client.get("/deploy")
        assert resp.status_code == 200 and resp.text == "<h1>Deploy</h1>"

    @pytest.mark.asyncio
    async def test_not_found(self, async_client: AsyncClient) -> None:
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        with patch("app.main.DEPLOY_HTML_PATH", mock_path):
            resp = await async_client.get("/deploy")
        assert resp.status_code == 404


class TestLifespanScheduler:
    @pytest.mark.asyncio
    async def test_starts_scheduler_when_enabled(self) -> None:
        from app.main import app, lifespan

        mock_sched = AsyncMock()
        with (
            patch("app.main.settings.scheduler_enabled", True),
            patch("app.scheduler.get_scheduler", return_value=mock_sched),
        ):
            async with lifespan(app):
                pass
        mock_sched.start.assert_awaited_once()


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_all_services_ok(self, async_client: AsyncClient) -> None:
        mock_conn = AsyncMock()
        mock_redis_client = AsyncMock()
        with (
            patch("asyncpg.connect", AsyncMock(return_value=mock_conn)),
            patch("redis.asyncio.from_url", return_value=mock_redis_client),
            patch("httpx.AsyncClient") as mock_cls,
        ):
            mock_instance = AsyncMock()
            mock_instance.get.return_value = MagicMock(status_code=200)
            mock_cls.return_value.__aenter__.return_value = mock_instance
            resp = await async_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["ollama"] == "ok"

    @pytest.mark.asyncio
    async def test_ollama_error_response(self, async_client: AsyncClient) -> None:
        mock_conn = AsyncMock()
        mock_redis_client = AsyncMock()
        with (
            patch("asyncpg.connect", AsyncMock(return_value=mock_conn)),
            patch("redis.asyncio.from_url", return_value=mock_redis_client),
            patch("httpx.AsyncClient") as mock_cls,
        ):
            mock_instance = AsyncMock()
            mock_instance.get.return_value = MagicMock(status_code=500)
            mock_cls.return_value.__aenter__.return_value = mock_instance
            resp = await async_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["ollama"] == "error"

    @pytest.mark.asyncio
    async def test_database_error_path(self, async_client: AsyncClient) -> None:
        mock_redis_client = AsyncMock()
        with (
            patch("asyncpg.connect", AsyncMock(side_effect=Exception("db down"))),
            patch("redis.asyncio.from_url", return_value=mock_redis_client),
        ):
            resp = await async_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["database"] == "error"

    @pytest.mark.asyncio
    async def test_redis_error_path(self, async_client: AsyncClient) -> None:
        mock_conn = AsyncMock()
        with (
            patch("asyncpg.connect", AsyncMock(return_value=mock_conn)),
            patch("redis.asyncio.from_url", side_effect=Exception("redis down")),
        ):
            resp = await async_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["redis"] == "error"


class TestDeployConfigure:
    @pytest.mark.asyncio
    async def test_no_repo_uses_commands(self, async_client: AsyncClient) -> None:
        mock_run = MagicMock()
        mock_run.returncode = 0
        with (
            patch.dict("os.environ", {"GITHUB_REPOSITORY": ""}),
            patch("app.main.subprocess.run", return_value=mock_run),
        ):
            resp = await async_client.post("/api/v1/deploy/configure", json={"host": "example.com"})
        assert resp.status_code == 200
        assert resp.json()["errors"] is None

    @pytest.mark.asyncio
    async def test_with_repo_success(self, async_client: AsyncClient) -> None:
        mock_run = MagicMock()
        mock_run.returncode = 0
        with (
            patch.dict("os.environ", {"GITHUB_REPOSITORY": "owner/repo"}),
            patch("app.main.subprocess.run", return_value=mock_run),
        ):
            resp = await async_client.post("/api/v1/deploy/configure", json={"host": "example.com"})
        assert resp.status_code == 200 and resp.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_with_repo_partial_errors(self, async_client: AsyncClient) -> None:
        mock_run = MagicMock()
        mock_run.returncode = 1
        mock_run.stderr = "auth failed"
        with (
            patch.dict("os.environ", {"GITHUB_REPOSITORY": "owner/repo"}),
            patch("app.main.subprocess.run", return_value=mock_run),
        ):
            resp = await async_client.post("/api/v1/deploy/configure", json={"host": "example.com"})
        assert resp.status_code == 200 and resp.json()["status"] == "partial"

    @pytest.mark.asyncio
    async def test_with_all_secret_fields(self, async_client: AsyncClient) -> None:
        mock_run = MagicMock()
        mock_run.returncode = 0
        body = {
            "host": "example.com",
            "user": "root",
            "key": "ssh-key",
            "openrouter_api_key": "sk-or1",
            "openai_api_key": "sk-oa1",
            "database_url": "postgres://db",
            "redis_url": "redis://r",
            "jwt_secret": "my-jwt",
        }
        with (
            patch.dict("os.environ", {"GITHUB_REPOSITORY": ""}),
            patch("app.main.subprocess.run", return_value=mock_run),
        ):
            resp = await async_client.post("/api/v1/deploy/configure", json=body)
        assert resp.status_code == 200 and resp.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_subprocess_raises_in_loop(self, async_client: AsyncClient) -> None:
        with (
            patch.dict("os.environ", {"GITHUB_REPOSITORY": "owner/repo"}),
            patch("app.main.subprocess.run", side_effect=Exception("gh not found")),
        ):
            resp = await async_client.post("/api/v1/deploy/configure", json={"host": "example.com"})
        assert resp.status_code == 200 and resp.json()["status"] == "partial"

    @pytest.mark.asyncio
    async def test_workflow_trigger_raises(self, async_client: AsyncClient) -> None:
        def _side_effect(*args: object, **kwargs: object) -> object:
            cmd = args[0]
            if "secret" in cmd:  # type: ignore[operator]
                result = MagicMock()
                result.returncode = 0
                return result
            raise Exception("workflow failed")

        with (
            patch.dict("os.environ", {"GITHUB_REPOSITORY": "owner/repo"}),
            patch("app.main.subprocess.run", side_effect=_side_effect),
        ):
            resp = await async_client.post("/api/v1/deploy/configure", json={"host": "example.com"})
        assert resp.status_code == 200 and resp.json()["status"] == "partial"


def _drain_until_pong(ws: Any) -> dict[str, Any]:
    data = ws.receive_json()
    while isinstance(data, dict) and data.get("type") != "pong":
        data = ws.receive_json()
    return data


class TestWebSocketLogs:
    def test_ping_pong(self) -> None:
        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app) as client:
            with client.websocket_connect("/ws/logs") as ws:
                ws.send_text("ping")
                data = _drain_until_pong(ws)
                assert data == {"type": "pong"}

    def test_send_log_failure_does_not_crash(self) -> None:
        """send_log catches send_json failure (covers lines 173-174)."""
        from unittest.mock import patch as mock_patch

        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app) as client:
            with client.websocket_connect("/ws/logs") as ws:
                ws.send_text("ping")
                data = _drain_until_pong(ws)
                assert data == {"type": "pong"}
                # Patch send_json to fail after pong succeeds
                # The broadcast will trigger send_log -> send_json which raises
                with mock_patch(
                    "starlette.websockets.WebSocket.send_json",
                    side_effect=Exception("send failed"),
                ):
                    from app.utils.logging import get_broadcaster

                    broadcaster = get_broadcaster()
                    import asyncio

                    # Create a task on the app's loop via log_action
                    # Fire broadcaster directly; the mock will raise
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    loop.run_until_complete(broadcaster.broadcast({"test": "record"}))
