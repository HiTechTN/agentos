from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.config.settings import Settings
from app.scheduler import ScheduledTask, Scheduler


class TestSettingsProperties:
    def test_resolved_database_url_without_explicit_url(self) -> None:
        settings = Settings(
            database_url=None,
            postgres_host="test-pg",
            postgres_user="usr",
            postgres_password="pwd",
            postgres_db="db",
            redis_url="memory://",
        )
        url = settings.resolved_database_url
        assert "usr:pwd@test-pg" in url
        assert url.endswith("/db")

    def test_resolved_redis_url_without_explicit_url(self) -> None:
        settings = Settings(
            redis_url=None,
            redis_host="test-rh",
            redis_port=9999,
            redis_password="secret",
            database_url="sqlite://",
        )
        url = settings.resolved_redis_url
        assert "secret@test-rh:9999/0" in url


class TestHealthCheckErrorPaths:
    @pytest.mark.asyncio
    async def test_database_error_sets_status_to_error(self, async_client: AsyncClient) -> None:
        with patch("asyncpg.connect", side_effect=Exception("db down")):
            resp = await async_client.get("/health")
        data = resp.json()
        assert data["database"] == "error"
        assert data["api"] == "ok"


class TestSchedulerTaskExecution:
    @pytest.mark.asyncio
    async def test_execute_task_handles_orchestrator_error(self) -> None:
        scheduler = Scheduler()
        task = ScheduledTask(
            name="test-task", cron="* * * * *", prompt="do something", task_id="t1"
        )

        mock_orch = AsyncMock()
        mock_orch.run = AsyncMock(side_effect=Exception("orchestrator failed"))
        mock_notif = AsyncMock()
        mock_notif.send = AsyncMock()

        with patch("app.scheduler.get_orchestrator", return_value=mock_orch), \
             patch("app.scheduler.get_notifications", return_value=mock_notif):
            await scheduler._execute_task(task)

        mock_orch.run.assert_awaited_once_with(prompt="do something", project_id="default")
        mock_notif.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_task_sends_notification_on_success(self) -> None:
        scheduler = Scheduler()
        task = ScheduledTask(
            name="test-task", cron="* * * * *", prompt="do something",
            project_id="proj-1", channel="slack", task_id="t2",
        )

        mock_orch = AsyncMock()
        mock_orch.run = AsyncMock(return_value={"status": "completed"})
        mock_notif = AsyncMock()
        mock_notif.send = AsyncMock()

        with patch("app.scheduler.get_orchestrator", return_value=mock_orch), \
             patch("app.scheduler.get_notifications", return_value=mock_notif):
            await scheduler._execute_task(task)

        mock_orch.run.assert_awaited_once_with(prompt="do something", project_id="proj-1")
        mock_notif.send.assert_awaited_once()
