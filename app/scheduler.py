import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from app.config.settings import get_settings
from app.utils.logging import get_logger
from app.utils.notifications import get_notifications
from app.orchestrator import get_orchestrator

logger = get_logger("scheduler")


class ScheduledTask:
    def __init__(self, name: str, cron: str, prompt: str, project_id: str = "default",
                 channel: str = "console", task_id: str = ""):
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

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "cron": self.cron,
            "project_id": self.project_id, "channel": self.channel,
            "enabled": self.enabled, "run_count": self.run_count,
        }


class Scheduler:
    def __init__(self):
        self.settings = get_settings()
        self._tasks: dict[str, ScheduledTask] = {}
        self._running = False

    async def start(self):
        self._running = True
        logger.log_action("scheduler", "started", "completed")
        asyncio.create_task(self._run_loop())

    async def stop(self):
        self._running = False
        logger.log_action("scheduler", "stopped", "completed")

    async def add_task(self, name: str, cron: str, prompt: str,
                       project_id: str = "default", channel: str = "console") -> str:
        task = ScheduledTask(name, cron, prompt, project_id, channel)
        self._tasks[task.id] = task
        logger.log_action("scheduler", "task_created", "completed", details={"name": name, "cron": cron})
        return task.id

    def remove_task(self, task_id: str) -> bool:
        if task_id in self._tasks:
            del self._tasks[task_id]
            logger.log_action("scheduler", "task_removed", "completed", details={"task_id": task_id})
            return True
        return False

    def list_tasks(self) -> list[dict]:
        return [t.to_dict() for t in self._tasks.values()]

    async def _run_loop(self):
        while self._running:
            try:
                now = datetime.now(timezone.utc).timestamp()
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

    async def _execute_task(self, task: ScheduledTask):
        logger.log_action("scheduler", "task_run", "started", details={"name": task.name, "task_id": task.id})
        try:
            orchestrator = get_orchestrator()
            result = await orchestrator.run(prompt=task.prompt, project_id=task.project_id)
            await get_notifications().send(
                task.channel,
                f"Task: {task.name}",
                f"Completed with status: {result.get('status', 'unknown')}",
                {"task_id": task.id, "project": task.project_id},
            )
            logger.log_action("scheduler", "task_run", "completed", details={"name": task.name, "status": result.get("status")})
        except Exception as e:
            logger.log_error("scheduler", "task_run", str(e), details={"name": task.name})


_scheduler: Scheduler | None = None


def get_scheduler() -> Scheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = Scheduler()
    return _scheduler
