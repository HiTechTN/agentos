"""Smart OpenRouter free model router with automatic failover and rate-limit tracking."""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.config.settings import get_settings
from app.utils.logging import get_logger

from .llm_models import FREE_MODELS, FreeModel, WorkType, detect_work_type
from .llm_rate_limiter import _is_available, _ModelUsage, _record_request, _usage, _usage_lock

logger = get_logger(__name__)


class SmartLLMRouter:
    """Routes LLM requests to the best available free OpenRouter model."""

    OPENROUTER_BASE = "https://openrouter.ai/api/v1"
    OLLAMA_FALLBACK_MODEL = "qwen2.5-coder:7b"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            settings = get_settings()
            self._client = httpx.AsyncClient(
                base_url=self.OPENROUTER_BASE,
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "HTTP-Referer": "https://github.com/HiTechTN/agentos",
                    "X-Title": "AgentOS",
                },
                timeout=httpx.Timeout(60.0, connect=10.0),
            )
        return self._client

    async def select_model(
        self,
        work_type: WorkType,
        requires_tools: bool = False,
        requires_vision: bool = False,
        min_context: int = 0,
    ) -> FreeModel | None:
        """Select the best available model for the given requirements."""
        candidates = FREE_MODELS.get(work_type, FREE_MODELS[WorkType.GENERAL])

        for model in candidates:
            if requires_tools and not model.supports_tools:
                continue
            if requires_vision and not model.supports_vision:
                continue
            if model.context_window < min_context:
                continue
            if await _is_available(model):
                logger.log_action(
                    "llm_router",
                    "model_selected",
                    "completed",
                    details={
                        "work_type": work_type.value,
                        "model": model.id,
                        "model_name": model.name,
                    },
                )
                return model

        logger.log_warn("llm_router", "no_free_model", str(work_type.value))
        return None

    async def complete(
        self,
        prompt: str = "",
        system: str = "",
        agent_name: str = "",
        work_type: WorkType | None = None,
        messages: list[dict[str, str]] | None = None,
        requires_tools: bool = False,
        requires_vision: bool = False,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Route a prompt through the best available free model with automatic fallback."""
        detected_type = work_type or detect_work_type(prompt, agent_name)
        candidates = FREE_MODELS.get(detected_type, FREE_MODELS[WorkType.GENERAL])

        msg_list: list[dict[str, str]] = []
        if system:
            msg_list.append({"role": "system", "content": system})
        if messages:
            msg_list.extend(messages)
        elif prompt:
            msg_list.append({"role": "user", "content": prompt})

        for model in candidates:
            if requires_tools and not model.supports_tools:
                continue
            if requires_vision and not model.supports_vision:
                continue
            if not await _is_available(model):
                continue

            try:
                response = await self._call_openrouter(
                    model_id=model.id,
                    messages=msg_list,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                await _record_request(model.id, success=True)

                response["_router"] = {
                    "work_type": detected_type,
                    "model_used": model.id,
                    "model_name": model.name,
                    "source": "openrouter_free",
                }
                logger.log_action(
                    "llm_router",
                    "llm_routed",
                    "completed",
                    details={
                        "work_type": detected_type.value,
                        "model": model.id,
                        "input_tokens": response.get("usage", {}).get("prompt_tokens", 0),
                        "output_tokens": response.get("usage", {}).get("completion_tokens", 0),
                    },
                )
                return response

            except httpx.HTTPStatusError as exc:
                await _record_request(model.id, success=False)
                if exc.response.status_code == 429:
                    logger.log_warn("llm_router", "model_rate_limited", str(model.id))
                    continue
                logger.log_error(
                    "llm_router",
                    "model_error",
                    f"OpenRouter {model.id} HTTP {exc.response.status_code}",
                )
                continue
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                await _record_request(model.id, success=False)
                logger.log_warn("llm_router", "model_timeout", f"{model.id}: {exc}")
                continue

        logger.log_warn(
            "llm_router",
            "ollama_fallback",
            f"Work type: {detected_type.value} \u2192 {self.OLLAMA_FALLBACK_MODEL}",
        )
        return await self._call_ollama(
            messages=msg_list,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def _call_openrouter(
        self,
        model_id: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Call the OpenRouter API."""
        client = await self._get_client()
        resp = await client.post(
            "/chat/completions",
            json={
                "model": model_id,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        resp.raise_for_status()
        return dict(resp.json())

    async def _call_ollama(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Fallback to local Ollama when all free models are exhausted."""
        try:
            settings = get_settings()
            async with httpx.AsyncClient(
                base_url=settings.ollama_base_url,
                timeout=httpx.Timeout(120.0),
            ) as client:
                resp = await client.post(
                    "/api/chat",
                    json={
                        "model": self.OLLAMA_FALLBACK_MODEL,
                        "messages": messages,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens,
                        },
                        "stream": False,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": data["message"]["content"],
                            }
                        }
                    ],
                    "usage": {},
                    "_router": {
                        "work_type": "unknown",
                        "model_used": self.OLLAMA_FALLBACK_MODEL,
                        "model_name": f"Ollama/{self.OLLAMA_FALLBACK_MODEL}",
                        "source": "ollama_fallback",
                    },
                }
        except Exception as exc:
            logger.log_error("llm_router", "ollama_fallback_failed", str(exc))
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": (
                                "I'm temporarily unavailable. All LLM providers are unreachable."
                            ),
                        }
                    }
                ],
                "usage": {},
                "_router": {
                    "work_type": "unknown",
                    "model_used": "degraded",
                    "model_name": "Degraded",
                    "source": "degraded",
                },
            }

    async def get_usage_report(self) -> dict[str, Any]:
        """Return current usage stats for all tracked models."""
        async with _usage_lock:
            return {
                model_id: {
                    "requests_this_minute": u.requests_this_minute,
                    "requests_today": u.requests_today,
                    "consecutive_errors": u.consecutive_errors,
                    "is_banned": u.is_banned_until > time.time(),
                }
                for model_id, u in _usage.items()
            }

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            try:
                await self._client.aclose()
            except RuntimeError:
                pass


smart_router = SmartLLMRouter()

__all__ = [
    "WorkType",
    "FreeModel",
    "FREE_MODELS",
    "SmartLLMRouter",
    "detect_work_type",
    "smart_router",
    "_usage",
    "_usage_lock",
    "_ModelUsage",
    "_is_available",
    "_record_request",
]
