from abc import ABC, abstractmethod
from typing import Any

import yaml

from app.config.settings import get_settings
from app.utils.api_clients import LLMClient, LLMUnavailableError
from app.utils.logging import get_logger
from app.utils.hitl_gateway import get_hitl_gateway, HITLPendingError


class AgentError(Exception):
    def __init__(self, code: str, message: str, detail: str = ""):
        self.code = code
        self.detail = detail
        super().__init__(message)


class ToolResult:
    def __init__(self, success: bool, data: Any, message: str = ""):
        self.success = success
        self.data = data
        self.message = message


class BaseAgent(ABC):
    name: str = "base"
    model: str = ""
    system_prompt: str = ""

    def __init__(self):
        self.settings = get_settings()
        self.llm = LLMClient()
        self.logger = get_logger(self.name)
        self._hitl = get_hitl_gateway()
        self._load_prompts()

    def _load_prompts(self):
        import os
        prompts_path = os.path.join(os.path.dirname(__file__), "..", "config", "prompts.yaml")
        try:
            with open(prompts_path) as f:
                data = yaml.safe_load(f)
                key = self.name.lower()
                if key in data:
                    self.system_prompt = data[key].get("system", self.system_prompt)
        except Exception:
            pass

    @property
    def effective_model(self) -> str:
        override_key = f"{self.name.upper()}_AGENT_MODEL"
        env_model = getattr(self.settings, override_key.lower(), "")
        return env_model or self.model

    async def execute(self, task: dict, session_id: str = "", trace_id: str = "") -> dict:
        action = task.get("action", "execute")
        task_params = task.get("params", {})

        self.logger.log_action(
            agent_id=self.name,
            action=action,
            status="started",
            trace_id=trace_id,
            project_id=session_id,
            details=task_params,
        )

        try:
            rag_context = await self._retrieve_context(session_id, task)
            if rag_context:
                task_params["rag_context"] = rag_context

            result = await self._run(action, task_params, session_id, trace_id)
            self.logger.log_action(
                agent_id=self.name,
                action=action,
                status="completed",
                trace_id=trace_id,
                project_id=session_id,
            )
            return {"agent": self.name, "action": action, "success": True, "result": result}
        except HITLPendingError as e:
            raise e
        except AgentError as e:
            self.logger.log_error(self.name, action, e.code, trace_id, session_id, {"detail": e.detail})
            return {"agent": self.name, "action": action, "success": False, "error": {"code": e.code, "message": str(e)}}
        except LLMUnavailableError as e:
            self.logger.log_error(self.name, action, "llm_unavailable", trace_id, session_id)
            return {"agent": self.name, "action": action, "success": False, "error": {"code": "LLM_UNAVAILABLE", "message": str(e)}, "degraded": True}
        except Exception as e:
            self.logger.log_error(self.name, action, "unexpected_error", trace_id, session_id, {"detail": str(e)})
            return {"agent": self.name, "action": action, "success": False, "error": {"code": "UNEXPECTED", "message": str(e)}}

    async def _retrieve_context(self, session_id: str, task: dict) -> str:
        try:
            from app.memory.vector_store import get_vector_store
            vs = get_vector_store()
            query = f"{task.get('action', '')}: {task.get('params', {}).get('prompt', '')}"
            results = await vs.search(session_id, query, top_k=3)
            if results:
                contexts = [r["content"][:500] for r in results if r.get("content")]
                if contexts:
                    return "\n---\n".join(contexts)
        except Exception:
            pass
        return ""

    @abstractmethod
    async def _run(self, action: str, params: dict, session_id: str, trace_id: str) -> Any:
        ...

    async def _llm_call(self, messages: list[dict], temperature: float = 0.7) -> str:
        response = await self.llm.chat(
            model=self.effective_model,
            messages=messages,
            temperature=temperature,
        )
        return response.content

    async def _llm_call_routed(self, task_type: str, messages: list[dict], temperature: float = 0.7) -> str:
        response = await self.llm.chat_with_model_selection(
            task_type=task_type,
            messages=messages,
            temperature=temperature,
        )
        return response.content

    async def _require_hitl(self, session_id: str, action: str, details: dict) -> dict:
        return await self._hitl.request_approval(
            session_id=session_id,
            agent_name=self.name,
            action=action,
            details=details,
        )
