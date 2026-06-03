"""Auto-Discovery Engine — fetches, classifies and stores free LLM models.

Pipeline:
  1. GET https://openrouter.ai/api/v1/models
  2. Filter: pricing.prompt == "0" AND pricing.completion == "0"
  3. Classify each model into WorkType(s) based on name, description, capabilities
  4. Benchmark: lightweight latency + availability test
  5. Upsert in discovered_models table
"""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

_WORK_TYPE_SIGNALS: dict[str, list[str]] = {
    "code_gen": [
        "coder",
        "code",
        "codestral",
        "starcoder",
        "deepseek-coder",
        "qwen.*coder",
        "wizard.*coder",
        "opencoder",
        "granite.*code",
    ],
    "code_agent": [
        "laguna",
        "agent",
        "agentic",
        "tool",
        "function",
    ],
    "reasoning": [
        "r1",
        "reason",
        "think",
        "o1",
        "o3",
        "deepseek-r",
        "reflection",
        "qwq",
        "sky-t1",
    ],
    "content": [
        "llama.*instruct",
        "mistral.*instruct",
        "gemma.*it",
        "solar",
        "nous",
        "hermes",
        "openhermes",
    ],
    "fast": [
        "flash",
        "small",
        "mini",
        "7b",
        "scout",
        "haiku",
        "nano",
        "phi",
        "tiny",
        "3b",
    ],
    "multimodal": [
        "vision",
        "vl",
        "minicpm-v",
        "llava",
        "pixtral",
        "qwen.*vl",
        "gemini",
        "claude.*sonnet",
        "gpt.*o",
    ],
    "debug": [
        "deepseek.*v.*flash",
        "qwen.*coder",
        "o1",
        "claude",
    ],
}

_PROVIDER_SIGNALS: dict[str, list[str]] = {
    "code_gen": ["qwen", "deepseek"],
    "reasoning": ["deepseek", "nvidia"],
    "content": ["meta-llama", "mistralai", "google"],
    "multimodal": ["google", "qwen", "openai"],
    "fast": ["mistralai", "qwen"],
    "general": ["nvidia", "nousresearch", "openrouter"],
}


@dataclass
class DiscoveredModel:
    """A free model discovered from OpenRouter API."""

    id: str
    name: str
    provider: str
    context_window: int
    supports_tools: bool = False
    supports_vision: bool = False
    supports_reasoning: bool = False
    supports_json_mode: bool = False
    max_output_tokens: int | None = None
    work_types: list[str] = field(default_factory=list)
    primary_work_type: str = "general"
    req_per_min: int = 20
    req_per_day: int = 200
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SyncSnapshot:
    """Result of a discovery sync cycle."""

    models_found: int = 0
    models_new: int = 0
    models_removed: int = 0
    models_updated: int = 0
    source: str = "scheduler"
    duration_ms: int = 0
    error: str | None = None


class ModelAutoClassifier:
    """Classifies free models into WorkTypes based on name and capabilities."""

    def classify(self, model: dict[str, Any]) -> DiscoveredModel:
        """Classify a raw OpenRouter model dict into a DiscoveredModel."""
        model_id: str = model.get("id", "")
        name: str = model.get("name", "")
        provider = model_id.split("/")[0] if "/" in model_id else "unknown"
        description: str = (model.get("description") or "").lower()

        arch = model.get("architecture", {})
        modality: str = arch.get("modality", "text->text")

        supports_tools = bool(
            model.get("supported_parameters")
            and "tools" in str(model.get("supported_parameters", []))
        )
        supports_vision = "image" in modality.lower() or "vision" in name.lower()
        supports_reasoning = any(
            kw in model_id.lower() for kw in ["r1", "reason", "think", "o1", "o3"]
        )
        supports_json_mode = bool(
            model.get("supported_parameters")
            and "response_format" in str(model.get("supported_parameters", []))
        )

        context_window = (
            model.get("context_length")
            or model.get("top_provider", {}).get("context_length")
            or 4096
        )
        max_output = model.get("top_provider", {}).get("max_completion_tokens")

        scores: dict[str, float] = {k: 0.0 for k in _WORK_TYPE_SIGNALS}
        text_to_match = f"{model_id} {name} {description}".lower()

        for work_type, patterns in _WORK_TYPE_SIGNALS.items():
            for pattern in patterns:
                if re.search(pattern, text_to_match):
                    scores[work_type] += 1.0

        for work_type, providers in _PROVIDER_SIGNALS.items():
            if provider in providers:
                scores[work_type] += 0.5

        if supports_tools:
            scores["code_agent"] += 0.8
            scores["code_gen"] += 0.3
        if supports_vision:
            scores["multimodal"] += 2.0
        if supports_reasoning:
            scores["reasoning"] += 2.0
        if context_window >= 500_000:
            scores["code_gen"] += 0.5
            scores["reasoning"] += 0.3

        threshold = 0.5
        work_types = [wt for wt, score in scores.items() if score >= threshold]
        if not work_types:
            work_types = ["general"]

        primary = max(scores, key=lambda k: scores[k])
        if scores[primary] < threshold:
            primary = "general"

        return DiscoveredModel(
            id=model_id,
            name=name,
            provider=provider,
            context_window=int(context_window),
            supports_tools=supports_tools,
            supports_vision=supports_vision,
            supports_reasoning=supports_reasoning,
            supports_json_mode=supports_json_mode,
            max_output_tokens=int(max_output) if max_output else None,
            work_types=work_types,
            primary_work_type=primary,
            raw_metadata=model,
        )


class ModelBenchmark:
    """Lightweight benchmark to validate model availability and latency."""

    BENCHMARK_PROMPT = "Reply with exactly: OK"
    TIMEOUT_SECONDS = 15.0
    MAX_LATENCY_MS = 10_000

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if not self._client or self._client.is_closed:
            settings = get_settings()
            self._client = httpx.AsyncClient(
                base_url="https://openrouter.ai/api/v1",
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "HTTP-Referer": "https://github.com/HiTechTN/agentos",
                    "X-Title": "AgentOS-Benchmark",
                },
                timeout=httpx.Timeout(self.TIMEOUT_SECONDS),
            )
        return self._client

    async def test(self, model_id: str) -> tuple[bool, float]:
        """Test model availability. Returns (is_available, latency_ms)."""
        client = await self._get_client()
        t0 = time.monotonic()
        try:
            resp = await client.post(
                "/chat/completions",
                json={
                    "model": model_id,
                    "messages": [{"role": "user", "content": self.BENCHMARK_PROMPT}],
                    "max_tokens": 5,
                    "temperature": 0.0,
                },
            )
            latency_ms = (time.monotonic() - t0) * 1000
            if resp.status_code == 200:
                return True, latency_ms
            logger.log_action(
                "benchmark",
                "failed",
                "warning",
                details={"model": model_id, "status": resp.status_code},
            )
            return False, latency_ms
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            latency_ms = (time.monotonic() - t0) * 1000
            logger.log_action(
                "benchmark", "timeout", "warning", details={"model": model_id, "error": str(exc)}
            )
            return False, latency_ms

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class ModelDiscoveryEngine:
    """Main orchestrator for free model auto-discovery."""

    def __init__(self, db_session: AsyncSession, run_benchmark: bool = False) -> None:
        self._db = db_session
        self._classifier = ModelAutoClassifier()
        self._benchmark = ModelBenchmark() if run_benchmark else None
        self._run_benchmark = run_benchmark

    async def sync(self, source: str = "scheduler") -> SyncSnapshot:
        """Full sync cycle: fetch classify benchmark upsert snapshot."""
        t0 = time.monotonic()
        snapshot = SyncSnapshot(source=source)

        try:
            raw_models = await self._fetch_free_models()
            snapshot.models_found = len(raw_models)
            logger.log_action(
                "discovery",
                "fetched",
                "completed",
                details={"total": len(raw_models), "source": source},
            )

            if not raw_models:
                snapshot.error = "No free models returned by API"
                await self._save_snapshot(snapshot)
                return snapshot

            classified: list[DiscoveredModel] = []
            for raw in raw_models:
                try:
                    classified.append(self._classifier.classify(raw))
                except Exception as exc:
                    logger.log_action(
                        "discovery",
                        "classification_error",
                        "warning",
                        details={"model_id": raw.get("id", "?"), "error": str(exc)},
                    )

            if self._run_benchmark and self._benchmark:
                classified = await self._benchmark_batch(classified[:10])

            existing_ids = await self._get_existing_ids()

            for model in classified:
                is_new = model.id not in existing_ids
                await self._upsert_model(model, is_new)
                if is_new:
                    snapshot.models_new += 1
                else:
                    snapshot.models_updated += 1

            current_ids = {m.id for m in classified}
            stale = existing_ids - current_ids
            for stale_id in stale:
                await self._disable_stale_model(stale_id)
                snapshot.models_removed += 1

            snapshot.duration_ms = int((time.monotonic() - t0) * 1000)
            logger.log_action(
                "discovery",
                "completed",
                "completed",
                details={
                    "found": snapshot.models_found,
                    "new": snapshot.models_new,
                    "updated": snapshot.models_updated,
                    "removed": snapshot.models_removed,
                    "duration_ms": snapshot.duration_ms,
                },
            )
        except Exception as exc:
            snapshot.error = str(exc)
            snapshot.duration_ms = int((time.monotonic() - t0) * 1000)
            logger.log_action("discovery", "failed", "error", details={"error": str(exc)})
        finally:
            if self._benchmark:
                await self._benchmark.close()

        await self._save_snapshot(snapshot)
        return snapshot

    async def _fetch_free_models(self) -> list[dict[str, Any]]:
        settings = get_settings()
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
        ) as client:
            resp = await client.get(OPENROUTER_MODELS_URL)
            resp.raise_for_status()
            data = resp.json()

        all_models: list[dict[str, Any]] = data.get("data", [])
        free_models = [
            m
            for m in all_models
            if (
                str(m.get("pricing", {}).get("prompt", "1")) == "0"
                and str(m.get("pricing", {}).get("completion", "1")) == "0"
                and m.get("id", "").endswith(":free")
            )
        ]
        logger.log_action(
            "discovery",
            "filtered",
            "completed",
            details={"total": len(all_models), "free": len(free_models)},
        )
        return free_models

    async def _benchmark_batch(self, models: list[DiscoveredModel]) -> list[DiscoveredModel]:
        results = []
        for model in models:
            ok, latency = await self._benchmark.test(model.id)  # type: ignore[union-attr]
            model.raw_metadata["_benchmark"] = {
                "available": ok,
                "latency_ms": round(latency, 1),
            }
            if ok:
                results.append(model)
                logger.log_action(
                    "benchmark",
                    "ok",
                    "completed",
                    details={"model": model.id, "latency_ms": round(latency, 1)},
                )
            else:
                logger.log_action(
                    "benchmark",
                    "skip",
                    "info",
                    details={"model": model.id, "reason": "unavailable"},
                )
        return results

    async def _get_existing_ids(self) -> set[str]:
        rows = await self._db.execute(
            sa.text("SELECT id FROM discovered_models WHERE is_free = true")
        )
        return {row[0] for row in rows.fetchall()}

    async def _upsert_model(self, model: DiscoveredModel, is_new: bool) -> None:
        benchmark = model.raw_metadata.get("_benchmark", {})
        avg_latency = benchmark.get("latency_ms") if benchmark else None
        is_benchmarked = bool(benchmark)

        await self._db.execute(
            sa.text("""
                INSERT INTO discovered_models (
                    id, name, provider, context_window,
                    supports_tools, supports_vision, supports_reasoning,
                    supports_json_mode, max_output_tokens,
                    work_types, primary_work_type,
                    is_free, is_active, is_benchmarked,
                    avg_latency_ms, raw_metadata, last_checked_at
                ) VALUES (
                    :id, :name, :provider, :ctx,
                    :tools, :vision, :reasoning, :json_mode, :max_out,
                    CAST(:work_types AS jsonb), :primary_wt,
                    true, true, :benchmarked,
                    :latency, CAST(:raw AS jsonb), NOW()
                )
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    provider = EXCLUDED.provider,
                    context_window = EXCLUDED.context_window,
                    supports_tools = EXCLUDED.supports_tools,
                    supports_vision = EXCLUDED.supports_vision,
                    supports_reasoning = EXCLUDED.supports_reasoning,
                    work_types = EXCLUDED.work_types,
                    primary_work_type = EXCLUDED.primary_work_type,
                    is_active = true,
                    is_benchmarked = EXCLUDED.is_benchmarked,
                    avg_latency_ms = COALESCE(
                        EXCLUDED.avg_latency_ms, discovered_models.avg_latency_ms
                    ),
                    raw_metadata = EXCLUDED.raw_metadata,
                    last_checked_at = NOW(),
                    updated_at = NOW()
            """),
            {
                "id": model.id,
                "name": model.name,
                "provider": model.provider,
                "ctx": model.context_window,
                "tools": model.supports_tools,
                "vision": model.supports_vision,
                "reasoning": model.supports_reasoning,
                "json_mode": model.supports_json_mode,
                "max_out": model.max_output_tokens,
                "work_types": json.dumps(model.work_types),
                "primary_wt": model.primary_work_type,
                "benchmarked": is_benchmarked,
                "latency": avg_latency,
                "raw": json.dumps(model.raw_metadata),
            },
        )
        await self._db.commit()

    async def _disable_stale_model(self, model_id: str) -> None:
        await self._db.execute(
            sa.text("""
                UPDATE discovered_models
                SET is_active = false,
                    disabled_reason = 'not_in_free_list',
                    updated_at = NOW()
                WHERE id = :id
            """),
            {"id": model_id},
        )
        await self._db.commit()
        logger.log_action("discovery", "disabled_stale", "info", details={"model_id": model_id})

    async def _save_snapshot(self, snapshot: SyncSnapshot) -> None:
        await self._db.execute(
            sa.text("""
                INSERT INTO discovery_snapshots (
                    id, models_found, models_new, models_removed,
                    models_updated, source, duration_ms, error
                ) VALUES (
                    :id, :found, :new, :removed, :updated,
                    :source, :duration, :error
                )
            """),
            {
                "id": str(uuid.uuid4()),
                "found": snapshot.models_found,
                "new": snapshot.models_new,
                "removed": snapshot.models_removed,
                "updated": snapshot.models_updated,
                "source": snapshot.source,
                "duration": snapshot.duration_ms,
                "error": snapshot.error,
            },
        )
        await self._db.commit()
