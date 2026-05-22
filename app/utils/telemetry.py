import uuid

from app.config.settings import get_settings


class Span:
    def __init__(self, name: str, trace_id: str = "", attributes: dict | None = None):
        self.name = name
        self.trace_id = trace_id or str(uuid.uuid4())
        self.span_id = str(uuid.uuid4())[:16]
        self.attributes = attributes or {}
        self.start = 0.0
        self.end = 0.0

    def __enter__(self):
        import time

        self.start = time.time()
        return self

    def __exit__(self, *args):
        import time

        self.end = time.time()

    @property
    def duration_ms(self) -> float:
        return (self.end - self.start) * 1000

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "name": self.name,
            "duration_ms": round(self.duration_ms, 2),
            "attributes": self.attributes,
        }


class OpenTelemetrySetup:
    def __init__(self):
        self.settings = get_settings()
        self.enabled = self.settings.otlp_enabled
        self._spans: list[Span] = []

    async def start_span(
        self, name: str, trace_id: str = "", attributes: dict | None = None
    ) -> Span:
        span = Span(name, trace_id, attributes)
        span.__enter__()
        return span

    async def end_span(self, span: Span):
        span.__exit__()
        self._spans.append(span)
        if self.enabled:
            await self._export(span)

    async def _export(self, span: Span):
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(
                    f"{self.settings.otlp_endpoint}/v1/traces",
                    json={
                        "resourceSpans": [
                            {
                                "resource": {
                                    "attributes": [
                                        {
                                            "key": "service.name",
                                            "value": {"stringValue": self.settings.service_name},
                                        }
                                    ]
                                },
                                "scopeSpans": [
                                    {
                                        "scope": {"name": "agentos"},
                                        "spans": [
                                            {
                                                "traceId": span.trace_id.replace("-", ""),
                                                "spanId": span.span_id,
                                                "name": span.name,
                                                "startTimeUnixNano": int(span.start * 1e9),
                                                "endTimeUnixNano": int(span.end * 1e9),
                                                "attributes": [
                                                    {"key": k, "value": {"stringValue": str(v)}}
                                                    for k, v in span.attributes.items()
                                                ],
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    },
                )
        except Exception:
            pass

    def get_spans(self, trace_id: str = "") -> list[dict]:
        if trace_id:
            return [s.to_dict() for s in self._spans if s.trace_id == trace_id]
        return [s.to_dict() for s in self._spans]


_telemetry: OpenTelemetrySetup | None = None


def get_telemetry() -> OpenTelemetrySetup:
    global _telemetry
    if _telemetry is None:
        _telemetry = OpenTelemetrySetup()
    return _telemetry
