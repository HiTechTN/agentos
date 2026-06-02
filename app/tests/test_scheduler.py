"""Tests for app/scheduler.py — Scheduler and ScheduledTask."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.scheduler import ScheduledTask, Scheduler

_NIGHTLY_MARKER = "__nightly_reflection__"


class TestScheduledTask:
    def test_should_run_enabled_and_matching(self) -> None:
        task = ScheduledTask("test", "* * * * *", "prompt")
        task.enabled = True
        now = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC).timestamp()
        assert task.should_run(now)

    def test_should_run_disabled_returns_false(self) -> None:
        task = ScheduledTask("test", "* * * * *", "prompt")
        task.enabled = False
        assert not task.should_run(1000.0)

    def test_should_run_invalid_cron_returns_false(self) -> None:
        task = ScheduledTask("test", "invalid", "prompt")
        assert not task.should_run(1000.0)

    def test_to_dict_returns_all_fields(self) -> None:
        task = ScheduledTask("test", "0 2 * * *", "prompt", project_id="p1", channel="email")
        d = task.to_dict()
        assert d["name"] == "test"
        assert d["cron"] == "0 2 * * *"
        assert d["project_id"] == "p1"
        assert d["channel"] == "email"


class TestSchedulerCore:
    @pytest.mark.asyncio
    async def test_add_and_remove_task(self) -> None:
        scheduler = Scheduler()
        task_id = await scheduler.add_task("test", "* * * * *", "do something")
        assert task_id in scheduler._tasks
        assert scheduler.remove_task(task_id) is True
        assert task_id not in scheduler._tasks

    @pytest.mark.asyncio
    async def test_remove_missing_task_returns_false(self) -> None:
        scheduler = Scheduler()
        assert scheduler.remove_task("nonexistent") is False

    @pytest.mark.asyncio
    async def test_list_tasks(self) -> None:
        scheduler = Scheduler()
        await scheduler.add_task("t1", "0 2 * * *", "prompt1")
        await scheduler.add_task("t2", "0 3 * * *", "prompt2")
        tasks = scheduler.list_tasks()
        assert len(tasks) == 2

    @pytest.mark.asyncio
    async def test_execute_nightly_reflection_calls_method(self) -> None:
        scheduler = Scheduler()
        task = ScheduledTask("nightly", "0 2 * * *", _NIGHTLY_MARKER)
        with patch.object(scheduler, "_run_nightly_reflection", new=AsyncMock()) as mock_reflect:
            await scheduler._execute_task(task)
            mock_reflect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_regular_task(self) -> None:
        scheduler = Scheduler()
        task = ScheduledTask("regular", "0 2 * * *", "do work")
        with (
            patch("app.scheduler.get_orchestrator") as mock_get_orch,
            patch("app.scheduler.get_notifications") as mock_get_notif,
        ):
            mock_orch = AsyncMock()
            mock_orch.run = AsyncMock(return_value={"status": "completed"})
            mock_get_orch.return_value = mock_orch

            mock_notif = AsyncMock()
            mock_get_notif.return_value = mock_notif

            await scheduler._execute_task(task)
            mock_orch.run.assert_awaited_once_with(prompt="do work", project_id="default")
            mock_notif.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_task_exception(self) -> None:
        scheduler = Scheduler()
        task = ScheduledTask("failing", "0 2 * * *", "boom")
        with patch("app.scheduler.get_orchestrator", side_effect=RuntimeError("oops")):
            await scheduler._execute_task(task)
        # Should not raise

    @pytest.mark.asyncio
    async def test_run_nightly_reflection_exception_caught(self) -> None:
        scheduler = Scheduler()
        with patch(
            "sqlalchemy.ext.asyncio.create_async_engine",
            side_effect=RuntimeError("db fail"),
        ):
            await scheduler._run_nightly_reflection()
        # Should not raise

    @pytest.mark.asyncio
    async def test_run_nightly_reflection_happy_path(self) -> None:
        scheduler = Scheduler()
        mock_engine = AsyncMock()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory = Mock(return_value=mock_session)

        mock_result = Mock()
        mock_result.fetchall.return_value = [("ws-1",), ("ws-2",)]
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_report = {"new_skills_discovered": 3}
        mock_reflection_engine = AsyncMock()
        mock_reflection_engine.run = AsyncMock(return_value=mock_report)
        mock_reflection_cls = Mock(return_value=mock_reflection_engine)

        with (
            patch("sqlalchemy.ext.asyncio.create_async_engine", return_value=mock_engine),
            patch("sqlalchemy.ext.asyncio.async_sessionmaker", return_value=mock_session_factory),
            patch("app.learning.reflection.SelfReflectionEngine", mock_reflection_cls),
        ):
            await scheduler._run_nightly_reflection()

        assert mock_reflection_cls.call_count == 2
        mock_reflection_cls.assert_any_call(db_session=mock_session, workspace_id="ws-1")
        mock_reflection_cls.assert_any_call(db_session=mock_session, workspace_id="ws-2")
