import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any


MASKED_FIELDS = {"api_key", "token", "password", "secret", "authorization"}


def _mask_sensitive(data: dict) -> dict:
    masked = {}
    for k, v in data.items():
        if any(f in k.lower() for f in MASKED_FIELDS):
            masked[k] = "***MASKED***"
        elif isinstance(v, dict):
            masked[k] = _mask_sensitive(v)
        else:
            masked[k] = v
    return masked


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
        details: dict | None = None,
    ) -> str:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
        return json.dumps(record, default=str)

    def log_action(
        self,
        agent_id: str,
        action: str,
        status: str,
        trace_id: str | None = None,
        project_id: str | None = None,
        details: dict | None = None,
    ) -> str:
        line = self._json_log("INFO", agent_id, action, status, trace_id, project_id, details)
        self.info(line)
        return line

    def log_error(
        self,
        agent_id: str,
        action: str,
        error: str,
        trace_id: str | None = None,
        project_id: str | None = None,
        details: dict | None = None,
    ) -> str:
        err_details = {"error": error, **(details or {})}
        line = self._json_log("ERROR", agent_id, action, "failed", trace_id, project_id, err_details)
        self.error(line)
        return line

    def log_warn(
        self,
        agent_id: str,
        action: str,
        message: str,
        trace_id: str | None = None,
        project_id: str | None = None,
    ) -> str:
        line = self._json_log("WARN", agent_id, action, "warning", trace_id, project_id, {"message": message})
        self.warning(line)
        return line


def get_logger(name: str = "agentos") -> AgentOSLogger:
    logging.setLoggerClass(AgentOSLogger)
    return logging.getLogger(name)
