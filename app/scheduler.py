import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from app.config.settings import get_settings
from app.orchestrator import get_orchestrator
from app.utils.logging import get_logger
from app.utils.notifications import get_notifications

logger = get_logger("scheduler")

_NIGHTLY_REFLECTION_MARKER = "__nightly_reflection__"


class ScheduledTask:
    def __init__(
        self,
        name: str,
        cron: str,
        prompt: str,
        project_id: str = "default",
        channel: str = "console",
        task_id: str = "",
    ):
        self.id = task_id or str(uuid.uuid4())[:8]
        self.name = name
        self.cron = cron
        self.prompt = prompt
        self.project_id = project_id
        self.channel = channel
        self.enabled = True
        self.last_run: float = 0.0
        self.run_count: int = 0

    def should_run(self, now: float) -> bool:
        if not self.enabled:
            return False
        parts = self.cron.split()
        if len(parts) < 5:
            return False
        try:
            from datetime import datetime

            dt = datetime.fromtimestamp(now)
            minute_ok = parts[0] == "*" or str(dt.minute) == parts[0]
            hour_ok = parts[1] == "*" or str(dt.hour) == parts[1]
            day_ok = parts[2] == "*" or str(dt.day) == parts[2]
            month_ok = parts[3] == "*" or str(dt.month) == parts[3]
            weekday_ok = parts[4] == "*" or str(dt.weekday()) == parts[4]
            return minute_ok and hour_ok and day_ok and month_ok and weekday_ok
        except Exception:
            return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "cron": self.cron,
            "project_id": self.project_id,
            "channel": self.channel,
            "enabled": self.enabled,
            "run_count": self.run_count,
        }


class Scheduler:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._tasks: dict[str, ScheduledTask] = {}
        self._running = False

    async def start(self) -> None:
        self._running = True
        cron = getattr(self.settings, "nightly_reflection_cron", "0 2 * * *")
        template = self._tasks.get("__nightly__")
        if not template:
            task = ScheduledTask("nightly_reflection", cron, _NIGHTLY_REFLECTION_MARKER)
            task.id = "__nightly__"
            self._tasks[task.id] = task
        logger.log_action("scheduler", "started", "completed")
        asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._running = False
        logger.log_action("scheduler", "stopped", "completed")

    async def add_task(
        self,
        name: str,
        cron: str,
        prompt: str,
        project_id: str = "default",
        channel: str = "console",
    ) -> str:
        task = ScheduledTask(name, cron, prompt, project_id, channel)
        self._tasks[task.id] = task
        logger.log_action(
            "scheduler", "task_created", "completed", details={"name": name, "cron": cron}
        )
        return task.id

    def remove_task(self, task_id: str) -> bool:
        if task_id in self._tasks:
            del self._tasks[task_id]
            logger.log_action(
                "scheduler", "task_removed", "completed", details={"task_id": task_id}
            )
            return True
        return False

    def list_tasks(self) -> list[dict[str, Any]]:
        return [t.to_dict() for t in self._tasks.values()]

    async def _run_loop(self) -> None:
        while self._running:
            try:
                now = datetime.now(UTC).timestamp()
                for task in list(self._tasks.values()):
                    if task.should_run(now) and (now - task.last_run) > 60:
                        task.last_run = now
                        task.run_count += 1
                        asyncio.create_task(self._execute_task(task))
                await asyncio.sleep(self.settings.scheduler_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.log_error("scheduler", "loop_error", str(e))
                await asyncio.sleep(30)

    async def _execute_task(self, task: ScheduledTask) -> None:
        logger.log_action(
            "scheduler", "task_run", "started", details={"name": task.name, "task_id": task.id}
        )
        try:
            if task.prompt == _NIGHTLY_REFLECTION_MARKER:
                await self._run_nightly_reflection()
                return
            orchestrator = get_orchestrator()
            result = await orchestrator.run(prompt=task.prompt, project_id=task.project_id)
            await get_notifications().send(
                task.channel,
                f"Task: {task.name}",
                f"Completed with status: {result.get('status', 'unknown')}",
                {"task_id": task.id, "project": task.project_id},
            )
            logger.log_action(
                "scheduler",
                "task_run",
                "completed",
                details={"name": task.name, "status": result.get("status")},
            )
        except Exception as e:
            logger.log_error("scheduler", "task_run", str(e), details={"name": task.name})

    async def _run_nightly_reflection(self) -> None:
        """Trigger self-reflection for all active workspaces."""
        try:
            from sqlalchemy import text as sa_text
            from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

            from app.config.settings import get_settings
            from app.learning.reflection import SelfReflectionEngine

            settings = get_settings()
            db_engine = create_async_engine(settings.resolved_database_url, echo=False)
            session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
            async with session_factory() as db:
                workspaces_result = await db.execute(
                    sa_text("SELECT DISTINCT workspace_id FROM episodic_memories")
                )
                workspace_ids = [r[0] for r in workspaces_result.fetchall()]
                for ws_id in workspace_ids or ["default"]:
                    eng = SelfReflectionEngine(db_session=db, workspace_id=ws_id)
                    report = await eng.run(force=True)
                    if report:
                        logger.log_action(
                            "scheduler",
                            "nightly_reflection_done",
                            "completed",
                            details={
                                "workspace": ws_id,
                                "new_skills": report["new_skills_discovered"],
                            },
                        )
        except Exception as e:
            logger.log_error("scheduler", "nightly_reflection", str(e))


_scheduler: Scheduler | None = None


def get_scheduler() -> Scheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = Scheduler()
    return _scheduler
