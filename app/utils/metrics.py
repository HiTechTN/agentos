from typing import Any

from app.config.settings import get_settings


class MetricsCollector:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._counters: dict[str, int] = {}
        self._timings: dict[str, list[float]] = {}
        self._gauges: dict[str, Any] = {}

    def inc(self, name: str, value: int = 1) -> None:
        self._counters[name] = self._counters.get(name, 0) + value

    def timing(self, name: str, duration: float) -> None:
        if name not in self._timings:
            self._timings[name] = []
        self._timings[name].append(duration)
        if len(self._timings[name]) > 1000:
            self._timings[name] = self._timings[name][-1000:]

    def gauge(self, name: str, value: Any) -> None:
        self._gauges[name] = value

    def render_prometheus(self) -> str:
        lines = [
            "# HELP agentos_metrics AgentOS application metrics",
            "# TYPE agentos_metrics untyped",
        ]
        for name, val in self._counters.items():
            lines.append(f"agentos_{name}_total {val}")
        for name, vals in self._timings.items():
            if vals:
                avg = sum(vals) / len(vals)
                lines.append(f"agentos_{name}_duration_seconds_avg {avg:.4f}")
                lines.append(f"agentos_{name}_duration_seconds_count {len(vals)}")
        for name, val in self._gauges.items():
            lines.append(f"agentos_{name} {val}")
        return "\n".join(lines) + "\n"


_metrics: MetricsCollector | None = None


def get_metrics() -> MetricsCollector:
    global _metrics
    if _metrics is None:
        _metrics = MetricsCollector()
    return _metrics
