import json
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

MASKED_FIELDS = {"api_key", "token", "password", "secret", "authorization"}


def _mask_sensitive(data: dict[str, Any]) -> dict[str, Any]:
    masked: dict[str, Any] = {}
    for k, v in data.items():
        if any(f in k.lower() for f in MASKED_FIELDS):
            masked[k] = "***MASKED***"
        elif isinstance(v, dict):
            masked[k] = _mask_sensitive(v)
        else:
            masked[k] = v
    return masked


class LogBroadcaster:
    """Simple in-process pub/sub for WebSocket broadcasting."""

    def __init__(self) -> None:
        self._subscribers: list[Callable[..., Any]] = []

    def subscribe(self, callback: Callable[..., Any]) -> None:
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[..., Any]) -> None:
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    async def broadcast(self, record: dict[str, Any]) -> None:
        for cb in self._subscribers:
            try:
                if hasattr(cb, "__call__"):
                    result = cb(record)
                    if hasattr(result, "__await__"):
                        await result
            except Exception:
                pass


_broadcaster = LogBroadcaster()


def get_broadcaster() -> LogBroadcaster:
    return _broadcaster


class AgentOSLogger(logging.Logger):
    def __init__(self, name: str, level: int = logging.INFO):
        super().__init__(name, level)
        self._handler = logging.StreamHandler()
        self._handler.setFormatter(logging.Formatter("%(message)s"))
        self.addHandler(self._handler)

    def _json_log(
        self,
        level: str,
        agent_id: str,
        action: str,
        status: str,
        trace_id: str | None = None,
        project_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        record: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": level,
            "logger": self.name,
            "agent_id": agent_id,
            "action": action,
            "status": status,
            "trace_id": trace_id or str(uuid.uuid4()),
            "project_id": project_id or "unknown",
        }
        if details:
            record["details"] = _mask_sensitive(details)
        return json.dumps(record, default=str), record

    def log_action(
        self,
        agent_id: str,
        action: str,
        status: str,
        trace_id: str | None = None,
        project_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> str:
        line, record = self._json_log(
            "INFO", agent_id, action, status, trace_id, project_id, details
        )
        self.info(line)
        try:
            import asyncio

            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_broadcaster.broadcast(record))
        except RuntimeError:
            pass
        return line

    def log_error(
        self,
        agent_id: str,
        action: str,
        error: str,
        trace_id: str | None = None,
        project_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> str:
        err_details: dict[str, Any] = {"error": error, **(details or {})}
        line, record = self._json_log(
            "ERROR", agent_id, action, "failed", trace_id, project_id, err_details
        )
        self.error(line)
        try:
            import asyncio

            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_broadcaster.broadcast(record))
        except RuntimeError:
            pass
        return line

    def log_warn(
        self,
        agent_id: str,
        action: str,
        message: str,
        trace_id: str | None = None,
        project_id: str | None = None,
    ) -> str:
        line, record = self._json_log(
            "WARN", agent_id, action, "warning", trace_id, project_id, {"message": message}
        )
        self.warning(line)
        try:
            import asyncio

            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_broadcaster.broadcast(record))
        except RuntimeError:
            pass
        return line


def get_logger(name: str = "agentos") -> AgentOSLogger:
    logging.setLoggerClass(AgentOSLogger)
    logger = logging.getLogger(name)
    assert isinstance(logger, AgentOSLogger)
    return logger
