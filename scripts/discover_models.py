#!/usr/bin/env python3
"""CLI script for manual model discovery and rotation management.

Usage:
    uv run python scripts/discover_models.py            sync only
    uv run python scripts/discover_models.py --bench    sync + benchmark
    uv run python scripts/discover_models.py --report   display catalog
    uv run python scripts/discover_models.py --reset    reset rotation weights
    uv run python scripts/discover_models.py --health   health check all models
    uv run python scripts/discover_models.py --disable <model_id>
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config.settings import get_settings


def _print_table(rows: list[list[str]], headers: list[str]) -> None:
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(cell))

    sep = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"
    fmt = "| " + " | ".join(f"{{:<{w}}}" for w in col_widths) + " |"

    print(sep)
    print(fmt.format(*headers))
    print(sep)
    for row in rows:
        padded = [row[i] if i < len(row) else "" for i in range(len(col_widths))]
        print(fmt.format(*padded))
    print(sep)


def _get_session() -> tuple[create_async_engine, async_sessionmaker[AsyncSession]]:  # type: ignore[type-arg]
    settings = get_settings()
    engine = create_async_engine(settings.resolved_database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


async def cmd_sync(bench: bool = False) -> None:
    from app.utils.model_discovery import ModelDiscoveryEngine

    print(" AgentOS — Model Auto-Discovery ")
    print("=" * 50)
    print("Fetching free models from OpenRouter API...")

    engine, factory = _get_session()
    async with factory() as session:
        disc = ModelDiscoveryEngine(db_session=session, run_benchmark=bench)
        snapshot = await disc.sync(source="manual_cli")

    print(f"\n Sync completed in {snapshot.duration_ms}ms")
    print(f"   Models found   : {snapshot.models_found}")
    print(f"   New models     : {snapshot.models_new}")
    print(f"   Updated        : {snapshot.models_updated}")
    print(f"   Removed        : {snapshot.models_removed}")
    if snapshot.error:
        print(f"\n Error: {snapshot.error}")
    await engine.dispose()


async def cmd_report() -> None:
    from app.utils.rotation_engine import RotationEngine

    engine, factory = _get_session()
    async with factory() as session:
        rot = RotationEngine(db_session=session)
        models = await rot.get_catalog()

    headers = [
        "Model ID",
        "Primary WT",
        "Context",
        "Tools",
        "Vision",
        "Weight",
        "Success%",
        "Latency",
        "Status",
    ]
    rows = []
    for m in models:
        total = m.get("total_requests") or 0
        errors = m.get("total_errors") or 0
        success_pct = f"{((total - errors) / total * 100):.0f}%" if total > 0 else "N/A"
        latency = m.get("avg_latency_ms")
        lat_str = f"{latency:.0f}ms" if latency else "-"

        if not m.get("is_active"):
            status = f"disabled:{m.get('disabled_reason', '?')}"
        elif m.get("is_rate_limited_until"):
            status = "rate-limited"
        else:
            status = "active"

        rows.append(
            [
                m["id"][:40],
                m.get("primary_work_type", "-"),
                f"{m.get('context_window', 0) // 1000}K",
                "Y" if m.get("supports_tools") else "N",
                "Y" if m.get("supports_vision") else "N",
                f"{m.get('rotation_weight', 1.0):.2f}",
                success_pct,
                lat_str,
                status,
            ]
        )

    _print_table(rows, headers)
    print(f"\nTotal: {len(models)} models")
    await engine.dispose()


async def cmd_health() -> None:
    from app.utils.model_discovery import ModelBenchmark
    from app.utils.rotation_engine import RotationEngine

    work_types = [
        "code_gen",
        "code_agent",
        "reasoning",
        "content",
        "fast",
        "debug",
        "multimodal",
        "general",
    ]

    engine, factory = _get_session()
    async with factory() as session:
        rot = RotationEngine(db_session=session)
        bench = ModelBenchmark()

        headers = ["WorkType", "Model", "Status", "Latency"]
        rows = []
        for wt in work_types:
            model = await rot.select_model(wt)
            if not model:
                rows.append([wt, "-", "NO MODEL", "-"])
                continue
            print(f"  Testing {model['id']}...", end=" ")
            ok, latency = await bench.test(model["id"])
            status = "OK" if ok else "FAIL"
            print(f"{status} ({latency:.0f}ms)")
            rows.append([wt, model["id"][:40], status, f"{latency:.0f}ms" if ok else "-"])

        await bench.close()
        print()
        _print_table(rows, headers)
    await engine.dispose()


async def cmd_reset() -> None:
    engine, factory = _get_session()
    async with factory() as session:
        await session.execute(sa_text("UPDATE discovered_models SET rotation_weight = 1.0"))
        await session.commit()
    print(" All rotation weights reset to 1.0")
    await engine.dispose()


async def cmd_disable(model_id: str) -> None:
    from app.utils.rotation_engine import RotationEngine

    engine, factory = _get_session()
    async with factory() as session:
        rot = RotationEngine(db_session=session)
        await rot.disable_model(model_id, reason="manual_cli")
    print(f" Model disabled: {model_id}")
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentOS  Free Model Discovery & Rotation CLI")
    parser.add_argument("--bench", action="store_true", help="Run benchmark after sync")
    parser.add_argument("--report", action="store_true", help="Display model catalog")
    parser.add_argument("--health", action="store_true", help="Health check top model per WorkType")
    parser.add_argument("--reset", action="store_true", help="Reset all rotation weights")
    parser.add_argument("--disable", metavar="MODEL_ID", help="Disable a specific model")
    args = parser.parse_args()

    if args.disable:
        asyncio.run(cmd_disable(args.disable))
    elif args.report:
        asyncio.run(cmd_report())
    elif args.health:
        asyncio.run(cmd_health())
    elif args.reset:
        asyncio.run(cmd_reset())
    else:
        asyncio.run(cmd_sync(bench=args.bench))


if __name__ == "__main__":
    main()
