"""Smart OpenRouter free model router for AgentOS.

Routes LLM calls to the best available free OpenRouter model
based on work type, with automatic failover and rate-limit tracking.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

from app.config.settings import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class WorkType(str, Enum):
    """Categories of LLM work — determines which free model is selected."""

    CODE_GEN = "code_gen"
    CODE_AGENT = "code_agent"
    REASONING = "reasoning"
    CONTENT = "content"
    FAST = "fast"
    MULTIMODAL = "multimodal"
    DEBUG = "debug"
    GENERAL = "general"


@dataclass
class FreeModel:
    """A single free OpenRouter model with its capabilities."""

    id: str
    name: str
    context_window: int
    supports_tools: bool = False
    supports_vision: bool = False
    supports_reasoning: bool = False
    req_per_min: int = 20
    req_per_day: int = 200


FREE_MODELS: dict[WorkType, list[FreeModel]] = {
    WorkType.CODE_GEN: [
        FreeModel(
            id="qwen/qwen3-coder:free",
            name="Qwen3 Coder",
            context_window=1_000_000,
            supports_tools=True,
        ),
        FreeModel(
            id="deepseek/deepseek-v4-flash:free",
            name="DeepSeek V4 Flash",
            context_window=1_000_000,
            supports_tools=True,
            supports_reasoning=True,
        ),
        FreeModel(
            id="openai/gpt-oss-120b:free",
            name="GPT-OSS 120B",
            context_window=128_000,
            supports_tools=True,
        ),
    ],
    WorkType.CODE_AGENT: [
        FreeModel(
            id="poolside/laguna-m1:free",
            name="Laguna M.1",
            context_window=128_000,
            supports_tools=True,
        ),
        FreeModel(
            id="qwen/qwen3-coder:free",
            name="Qwen3 Coder",
            context_window=1_000_000,
            supports_tools=True,
        ),
        FreeModel(
            id="openai/gpt-oss-120b:free",
            name="GPT-OSS 120B",
            context_window=128_000,
            supports_tools=True,
        ),
    ],
    WorkType.REASONING: [
        FreeModel(
            id="deepseek/deepseek-r1:free",
            name="DeepSeek R1",
            context_window=128_000,
            supports_reasoning=True,
        ),
        FreeModel(
            id="google/gemini-2.0-pro:free",
            name="Gemini 2.0 Pro",
            context_window=2_000_000,
            supports_tools=True,
            supports_vision=True,
        ),
        FreeModel(
            id="nvidia/llama-3.1-nemotron-70b-instruct:free",
            name="Nemotron 70B",
            context_window=128_000,
        ),
    ],
    WorkType.CONTENT: [
        FreeModel(
            id="google/gemini-2.0-flash:free",
            name="Gemini 2.0 Flash",
            context_window=1_048_576,
            supports_tools=True,
            supports_vision=True,
        ),
        FreeModel(
            id="meta-llama/llama-3.3-70b-instruct:free",
            name="Llama 3.3 70B",
            context_window=128_000,
            supports_tools=True,
        ),
        FreeModel(
            id="mistralai/mistral-small-3:free",
            name="Mistral Small 3",
            context_window=32_000,
            supports_tools=True,
        ),
    ],
    WorkType.FAST: [
        FreeModel(
            id="mistralai/mistral-small-3:free",
            name="Mistral Small 3",
            context_window=32_000,
            supports_tools=True,
        ),
        FreeModel(
            id="qwen/qwen-2.5-7b-instruct:free",
            name="Qwen 2.5 7B",
            context_window=128_000,
        ),
        FreeModel(
            id="google/gemini-2.0-flash:free",
            name="Gemini 2.0 Flash",
            context_window=1_048_576,
            supports_tools=True,
        ),
    ],
    WorkType.MULTIMODAL: [
        FreeModel(
            id="qwen/qwen-2.5-vl-72b-instruct:free",
            name="Qwen 2.5 VL 72B",
            context_window=128_000,
            supports_vision=True,
        ),
        FreeModel(
            id="google/gemini-2.0-flash:free",
            name="Gemini 2.0 Flash",
            context_window=1_048_576,
            supports_tools=True,
            supports_vision=True,
        ),
        FreeModel(
            id="google/gemini-2.0-pro:free",
            name="Gemini 2.0 Pro",
            context_window=2_000_000,
            supports_vision=True,
        ),
    ],
    WorkType.DEBUG: [
        FreeModel(
            id="deepseek/deepseek-v4-flash:free",
            name="DeepSeek V4 Flash",
            context_window=1_000_000,
            supports_tools=True,
            supports_reasoning=True,
        ),
        FreeModel(
            id="qwen/qwen3-coder:free",
            name="Qwen3 Coder",
            context_window=1_000_000,
            supports_tools=True,
        ),
        FreeModel(
            id="deepseek/deepseek-r1:free",
            name="DeepSeek R1",
            context_window=128_000,
            supports_reasoning=True,
        ),
    ],
    WorkType.GENERAL: [
        FreeModel(
            id="nvidia/llama-3.1-nemotron-70b-instruct:free",
            name="Nemotron 70B",
            context_window=128_000,
        ),
        FreeModel(
            id="meta-llama/llama-3.3-70b-instruct:free",
            name="Llama 3.3 70B",
            context_window=128_000,
            supports_tools=True,
        ),
        FreeModel(
            id="openrouter/free",
            name="OpenRouter Auto",
            context_window=200_000,
            supports_tools=True,
        ),
    ],
}


_WORK_TYPE_KEYWORDS: dict[WorkType, list[str]] = {
    WorkType.CODE_GEN: [
        "scaffold", "implement", "refactor", "generate code",
        "write function", "create class", "write tests",
        "fix bug", "code generation",
    ],
    WorkType.CODE_AGENT: [
        "agent", "agentic", "multi-step", "tool call",
        "workflow", "pipeline", "automate",
    ],
    WorkType.REASONING: [
        "plan", "architecture", "design", "analyze", "reason",
        "compare", "evaluate", "strategy", "structured plan",
        "phases", "dependencies",
    ],
    WorkType.CONTENT: [
        "seo", "copy", "blog", "article", "social media",
        "marketing", "email campaign", "content", "write",
    ],
    WorkType.FAST: [
        "classify", "extract", "summarize", "translate",
        "quick", "fast", "short",
    ],
    WorkType.MULTIMODAL: [
        "image", "vision", "screenshot", "photo", "visual",
        "describe image", "analyze image",
    ],
    WorkType.DEBUG: [
        "debug", "error", "exception", "traceback", "crash",
        "fix error", "stack trace", "why is", "not working",
    ],
}


def detect_work_type(prompt: str, agent_name: str = "") -> WorkType:
    """Infer the WorkType from prompt content and agent name."""
    text = (prompt + " " + agent_name).lower()

    agent_map: dict[str, WorkType] = {
        "devagent": WorkType.CODE_AGENT,
        "contentagent": WorkType.CONTENT,
        "marketingagent": WorkType.CONTENT,
        "commerceagent": WorkType.REASONING,
        "@planner": WorkType.REASONING,
        "@verifier": WorkType.CODE_GEN,
        "@explorer": WorkType.FAST,
        "@codereviewer": WorkType.CODE_GEN,
        "@debugger": WorkType.DEBUG,
    }
    for agent_key, work_type in agent_map.items():
        if agent_key in text:
            return work_type

    scores: dict[WorkType, int] = {wt: 0 for wt in WorkType}
    for work_type, keywords in _WORK_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                scores[work_type] += 1

    best = max(scores, key=lambda k: scores[k])
    if scores[best] > 0:
        return best

    return WorkType.GENERAL


@dataclass
class _ModelUsage:
    """Track per-model usage for rate limiting."""

    requests_this_minute: int = 0
    requests_today: int = 0
    minute_window_start: float = field(default_factory=time.time)
    day_window_start: float = field(default_factory=time.time)
    consecutive_errors: int = 0
    last_error_time: float = 0.0
    is_banned_until: float = 0.0


_usage: dict[str, _ModelUsage] = {}
_usage_lock = asyncio.Lock()


async def _get_usage(model_id: str) -> _ModelUsage:
    async with _usage_lock:
        if model_id not in _usage:
            _usage[model_id] = _ModelUsage()
        return _usage[model_id]


async def _is_available(model: FreeModel) -> bool:
    """Return True if the model is not rate-limited or temporarily banned."""
    usage = await _get_usage(model.id)
    now = time.time()

    if usage.is_banned_until > now:
        return False

    if now - usage.minute_window_start >= 60:
        usage.requests_this_minute = 0
        usage.minute_window_start = now

    if now - usage.day_window_start >= 86_400:
        usage.requests_today = 0
        usage.day_window_start = now

    return (
        usage.requests_this_minute < model.req_per_min - 2
        and usage.requests_today < model.req_per_day - 5
    )


async def _record_request(model_id: str, success: bool) -> None:
    """Record a request and update error tracking."""
    usage = await _get_usage(model_id)
    usage.requests_this_minute += 1
    usage.requests_today += 1

    if success:
        usage.consecutive_errors = 0
    else:
        usage.consecutive_errors += 1
        usage.last_error_time = time.time()
        if usage.consecutive_errors >= 3:
            usage.is_banned_until = time.time() + 300
            logger.log_warn(
                "llm_router", "model_banned",
                f"Model {model_id} banned until {usage.is_banned_until}",
            )


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
                    "llm_router", "model_selected", "completed",
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
        """Complete a prompt using the best available free model.

        Args:
            prompt: The user message (ignored if messages is provided).
            system: Optional system prompt.
            agent_name: Agent name for WorkType detection.
            work_type: Force a specific WorkType (auto-detected if None).
            messages: Full message history (overrides prompt if provided).
            requires_tools: Require tool-calling support.
            requires_vision: Require vision/image support.
            temperature: Sampling temperature (0.0-1.0).
            max_tokens: Maximum tokens to generate.

        Returns:
            OpenAI-compatible response dict with extra metadata fields.
        """
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
                    "llm_router", "llm_routed", "completed",
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
                    "llm_router", "model_error",
                    f"OpenRouter {model.id} HTTP {exc.response.status_code}",
                )
                continue
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                await _record_request(model.id, success=False)
                logger.log_warn("llm_router", "model_timeout", f"{model.id}: {exc}")
                continue

        logger.log_warn(
            "llm_router", "ollama_fallback",
            f"Work type: {detected_type.value} → {self.OLLAMA_FALLBACK_MODEL}",
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
                                "I'm temporarily unavailable. "
                                "All LLM providers are unreachable."
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
            await self._client.aclose()


smart_router = SmartLLMRouter()

__all__ = [
    "WorkType",
    "FreeModel",
    "FREE_MODELS",
    "SmartLLMRouter",
    "detect_work_type",
    "smart_router",
]
