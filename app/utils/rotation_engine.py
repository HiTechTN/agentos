"""Smart Rotation Engine — selects the best available free model dynamically.

Rotation strategy:
  1. Query discovered_models for active models matching work_type
  2. Filter out: rate-limited, high-error-rate (> 30%), slow (> 8s latency)
  3. Score each candidate: quality_score * 0.5 + rotation_weight * 0.3 + latency_score * 0.2
  4. Select top candidate (weighted random from top 3 for diversity)
  5. On 429 mark rate-limited, rotate immediately to next
  6. On error decrement rotation_weight, log to rotation_log
  7. On success increment rotation_weight (capped at 3.0)
"""

from __future__ import annotations

import random
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.logging import get_logger

logger = get_logger(__name__)

MAX_ERROR_RATE = 0.30
MAX_LATENCY_MS = 8_000.0
RATE_LIMIT_BAN_MINUTES = 5
WEIGHT_MAX = 3.0
WEIGHT_MIN = 0.1
WEIGHT_SUCCESS_DELTA = 0.05
WEIGHT_ERROR_DELTA = -0.20
WEIGHT_RATELIMIT_DELTA = -0.15


class RotationEngine:
    """Dynamic model selection with learning-based rotation weights."""

    def __init__(self, db_session: AsyncSession) -> None:
        self._db = db_session
        self._in_memory_bans: dict[str, float] = {}

    async def select_model(
        self,
        work_type: str,
        requires_tools: bool = False,
        requires_vision: bool = False,
        min_context: int = 0,
    ) -> dict[str, Any] | None:
        """Select the best available model for the given requirements."""
        rows = await self._db.execute(
            sa.text("""
                SELECT id, name, provider, context_window,
                       supports_tools, supports_vision,
                       avg_latency_ms, success_rate, quality_score,
                       rotation_weight, total_requests, total_errors,
                       is_rate_limited_until
                FROM discovered_models
                WHERE is_active = true
                  AND is_free = true
                  AND (
                    primary_work_type = :wt
                    OR work_types::text ILIKE :wt_like
                  )
                  AND (is_rate_limited_until IS NULL
                       OR is_rate_limited_until < NOW())
                ORDER BY rotation_weight DESC, quality_score DESC
                LIMIT 20
            """),
            {"wt": work_type, "wt_like": f'%"{work_type}"%'},
        )
        candidates = [dict(r._mapping) for r in rows.fetchall()]

        filtered = []
        for c in candidates:
            if requires_tools and not c["supports_tools"]:
                continue
            if requires_vision and not c["supports_vision"]:
                continue
            if min_context and (c["context_window"] or 0) < min_context:
                continue
            if self._is_banned(c["id"]):
                continue
            total = c.get("total_requests") or 0
            errors = c.get("total_errors") or 0
            if total > 10 and errors / total > MAX_ERROR_RATE:
                continue
            latency = c.get("avg_latency_ms")
            if latency and latency > MAX_LATENCY_MS:
                continue
            filtered.append(c)

        if not filtered:
            logger.log_action(
                "rotation", "no_candidates", "warning", details={"work_type": work_type}
            )
            return None

        top3 = filtered[:3]
        weights = [max(c["rotation_weight"] or 1.0, 0.1) for c in top3]
        selected = random.choices(top3, weights=weights, k=1)[0]

        logger.log_action(
            "rotation",
            "selected",
            "completed",
            details={
                "model": selected["id"],
                "work_type": work_type,
                "weight": selected["rotation_weight"],
            },
        )
        return selected

    async def record_success(self, model_id: str, work_type: str, latency_ms: int) -> None:
        """Record a successful model call and update weights."""
        self._in_memory_bans.pop(model_id, None)

        await self._db.execute(
            sa.text("""
                UPDATE discovered_models SET
                    total_requests = total_requests + 1,
                    rotation_weight = LEAST(:max_w, rotation_weight + :delta),
                    success_rate = (success_rate * total_requests + 1.0) / (total_requests + 1),
                    avg_latency_ms = CASE
                        WHEN avg_latency_ms IS NULL THEN :latency
                        ELSE (avg_latency_ms * 0.8 + :latency * 0.2)
                    END,
                    last_used_at = NOW(),
                    updated_at = NOW()
                WHERE id = :id
            """),
            {
                "id": model_id,
                "delta": WEIGHT_SUCCESS_DELTA,
                "max_w": WEIGHT_MAX,
                "latency": latency_ms,
            },
        )
        await self._db.commit()
        await self._log_rotation(model_id, work_type, "selected", latency_ms, True)

    async def record_error(
        self, model_id: str, work_type: str, error_code: str, rotated_to: str | None = None
    ) -> None:
        """Record an error and decrement rotation weight."""
        await self._db.execute(
            sa.text("""
                UPDATE discovered_models SET
                    total_requests = total_requests + 1,
                    total_errors = total_errors + 1,
                    rotation_weight = GREATEST(:min_w, rotation_weight + :delta),
                    success_rate = success_rate * total_requests / (total_requests + 1),
                    updated_at = NOW()
                WHERE id = :id
            """),
            {"id": model_id, "delta": WEIGHT_ERROR_DELTA, "min_w": WEIGHT_MIN},
        )
        await self._db.commit()
        await self._log_rotation(model_id, work_type, "error", None, False, error_code, rotated_to)

    async def record_rate_limit(
        self, model_id: str, work_type: str, ban_minutes: int = RATE_LIMIT_BAN_MINUTES
    ) -> None:
        """Temporarily ban a model after receiving a 429 response."""
        ban_until = datetime.now(UTC) + timedelta(minutes=ban_minutes)
        self._in_memory_bans[model_id] = ban_until.timestamp()

        await self._db.execute(
            sa.text("""
                UPDATE discovered_models SET
                    is_rate_limited_until = :ban_until,
                    rotation_weight = GREATEST(:min_w, rotation_weight + :delta),
                    updated_at = NOW()
                WHERE id = :id
            """),
            {
                "id": model_id,
                "ban_until": ban_until,
                "delta": WEIGHT_RATELIMIT_DELTA,
                "min_w": WEIGHT_MIN,
            },
        )
        await self._db.commit()
        logger.log_action(
            "rotation",
            "rate_limited",
            "warning",
            details={"model": model_id, "ban_minutes": ban_minutes},
        )
        await self._log_rotation(model_id, work_type, "rate_limited", None, False, "429")

    async def disable_model(self, model_id: str, reason: str = "manual") -> None:
        """Permanently disable a model."""
        await self._db.execute(
            sa.text(
                "UPDATE discovered_models SET is_active = false, disabled_reason = :reason, updated_at = NOW() WHERE id = :id"  # noqa: E501
            ),
            {"id": model_id, "reason": reason},
        )
        await self._db.commit()
        self._in_memory_bans[model_id] = float("inf")
        logger.log_action(
            "rotation", "disabled", "info", details={"model_id": model_id, "reason": reason}
        )

    async def get_catalog(
        self, work_type: str | None = None, active_only: bool = True
    ) -> list[dict[str, Any]]:
        """Return the full model catalog with performance stats."""
        q = "SELECT * FROM discovered_models WHERE 1=1"
        params: dict[str, Any] = {}
        if active_only:
            q += " AND is_active = true"
        if work_type:
            q += " AND (primary_work_type = :wt OR work_types::text ILIKE :wt_like)"
            params["wt"] = work_type
            params["wt_like"] = f'%"{work_type}"%'
        q += " ORDER BY rotation_weight DESC, quality_score DESC"
        rows = await self._db.execute(sa.text(q), params)
        return [dict(r._mapping) for r in rows.fetchall()]

    async def get_rotation_stats(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return recent rotation log entries."""
        rows = await self._db.execute(
            sa.text("""
                SELECT model_id, work_type, reason, latency_ms,
                       success, error_code, rotated_to, created_at
                FROM model_rotation_log
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"limit": limit},
        )
        return [dict(r._mapping) for r in rows.fetchall()]

    def _is_banned(self, model_id: str) -> bool:
        ban_until = self._in_memory_bans.get(model_id)
        if ban_until is None:
            return False
        if ban_until == float("inf"):
            return True
        if time.time() > ban_until:
            del self._in_memory_bans[model_id]
            return False
        return True

    async def _log_rotation(
        self,
        model_id: str,
        work_type: str,
        reason: str,
        latency_ms: int | None,
        success: bool,
        error_code: str | None = None,
        rotated_to: str | None = None,
    ) -> None:
        await self._db.execute(
            sa.text("""
                INSERT INTO model_rotation_log (
                    id, model_id, work_type, reason,
                    latency_ms, success, error_code, rotated_to
                ) VALUES (
                    :id, :model_id, :work_type, :reason,
                    :latency_ms, :success, :error_code, :rotated_to
                )
            """),
            {
                "id": str(uuid.uuid4()),
                "model_id": model_id,
                "work_type": work_type,
                "reason": reason,
                "latency_ms": latency_ms,
                "success": success,
                "error_code": error_code,
                "rotated_to": rotated_to,
            },
        )
        await self._db.commit()
