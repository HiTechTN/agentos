"""Tests for rate limiting configuration."""

from __future__ import annotations

from app.utils.rate_limit import LIMITS


class TestRateLimitConfig:
    def test_run_limit_defined(self) -> None:
        assert "run" in LIMITS
        assert "/" in LIMITS["run"]

    def test_plan_limit_defined(self) -> None:
        assert "plan" in LIMITS

    def test_verify_limit_defined(self) -> None:
        assert "verify" in LIMITS

    def test_default_limit_defined(self) -> None:
        assert "default" in LIMITS

    def test_run_limit_more_restrictive_than_default(self) -> None:
        run_count = int(LIMITS["run"].split("/")[0])
        default_count = int(LIMITS["default"].split("/")[0])
        assert run_count < default_count
