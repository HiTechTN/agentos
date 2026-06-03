"""Tests for ModelDiscoveryEngine, ModelAutoClassifier, ModelBenchmark."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.utils.model_discovery import (
    ModelAutoClassifier,
    ModelBenchmark,
    ModelDiscoveryEngine,
    SyncSnapshot,
)


@pytest.fixture()
def mock_db() -> MagicMock:
    return AsyncMock()


@pytest.fixture()
def engine(mock_db: MagicMock) -> ModelDiscoveryEngine:
    return ModelDiscoveryEngine(db_session=mock_db, run_benchmark=False)


@pytest.fixture()
def classifier() -> ModelAutoClassifier:
    return ModelAutoClassifier()


class TestModelAutoClassifier:
    @pytest.fixture()
    def make_model(self) -> callable:
        def _make(overrides: dict | None = None) -> dict:
            base = {
                "id": "test/model:free",
                "name": "Test Model",
                "pricing": {"prompt": "0", "completion": "0"},
                "context_length": 8192,
                "description": "A test model",
                "top_provider": {"max_completion_tokens": 4096},
            }
            if overrides:
                base.update(overrides)
            return base

        return _make

    def test_classify_code_gen(self, classifier: ModelAutoClassifier, make_model: callable) -> None:
        m = classifier.classify(make_model({"id": "test/coder-model:free", "name": "Coder Model"}))
        assert m.primary_work_type == "code_gen"

    def test_classify_code_agent(
        self, classifier: ModelAutoClassifier, make_model: callable
    ) -> None:
        m = classifier.classify(make_model({"id": "test/agent-model:free", "name": "Agent Model"}))
        assert m.primary_work_type == "code_agent"

    def test_classify_reasoning(
        self, classifier: ModelAutoClassifier, make_model: callable
    ) -> None:
        m = classifier.classify(
            make_model({"id": "test/deepseek-r1:free", "name": "Reasoning Model"})
        )
        assert m.primary_work_type == "reasoning"

    def test_classify_content(self, classifier: ModelAutoClassifier, make_model: callable) -> None:
        m = classifier.classify(
            make_model({"id": "test/llama-instruct:free", "name": "Content Model"})
        )
        assert m.primary_work_type == "content"

    def test_classify_fast(self, classifier: ModelAutoClassifier, make_model: callable) -> None:
        m = classifier.classify(make_model({"id": "test/flash-model:free", "name": "Fast Model"}))
        assert m.primary_work_type == "fast"

    def test_classify_multimodal(
        self, classifier: ModelAutoClassifier, make_model: callable
    ) -> None:
        m = classifier.classify(
            make_model({"id": "test/vision-model:free", "name": "Vision Model"})
        )
        assert m.primary_work_type == "multimodal"

    def test_classify_debug(self, classifier: ModelAutoClassifier, make_model: callable) -> None:
        m = classifier.classify(
            make_model({"id": "test/claude-model:free", "name": "Claude Model"})
        )
        assert m.primary_work_type == "debug"

    def test_classify_general_fallback(
        self, classifier: ModelAutoClassifier, make_model: callable
    ) -> None:
        m = classifier.classify(make_model({"id": "test/generic:free", "name": "Generic AI Model"}))
        assert m.primary_work_type == "general"

    def test_classify_supports_vision(
        self, classifier: ModelAutoClassifier, make_model: callable
    ) -> None:
        m = classifier.classify(
            make_model(
                {
                    "id": "test/vision:free",
                    "architecture": {"modality": "image->text"},
                }
            )
        )
        assert m.supports_vision is True

    def test_classify_context_window(
        self, classifier: ModelAutoClassifier, make_model: callable
    ) -> None:
        m = classifier.classify(make_model({"context_length": 16384}))
        assert m.context_window == 16384

    def test_classify_missing_context(
        self, classifier: ModelAutoClassifier, make_model: callable
    ) -> None:
        m = classifier.classify(make_model({"context_length": None, "top_provider": {}}))
        assert m.context_window == 4096

    def test_classify_provider_scoring(
        self, classifier: ModelAutoClassifier, make_model: callable
    ) -> None:
        m = classifier.classify(
            make_model({"id": "deepseek/test-model:free", "name": "Test Model"})
        )
        assert m.provider == "deepseek"

    def test_classify_supports_tools(
        self, classifier: ModelAutoClassifier, make_model: callable
    ) -> None:
        m = classifier.classify(make_model({"supported_parameters": ["tools", "response_format"]}))
        assert m.supports_tools is True
        assert m.supports_json_mode is True

    def test_classify_large_context(
        self, classifier: ModelAutoClassifier, make_model: callable
    ) -> None:
        m = classifier.classify(make_model({"context_length": 1000000}))
        assert m.context_window == 1000000

    def test_classify_supports_reasoning(
        self, classifier: ModelAutoClassifier, make_model: callable
    ) -> None:
        m = classifier.classify(make_model({"id": "test/r1-reason-model:free", "name": "R1 Model"}))
        assert m.supports_reasoning is True


class TestModelBenchmark:
    @pytest.fixture()
    def bench(self) -> ModelBenchmark:
        return ModelBenchmark()

    @pytest.mark.asyncio
    async def test_test_success(self, bench: ModelBenchmark) -> None:
        mock_client = MagicMock()
        mock_client.post = AsyncMock()
        mock_client.post.return_value.status_code = 200
        mock_client.post.return_value.json = MagicMock(
            return_value={"choices": [{"message": {"content": "hi"}}]}
        )

        with patch.object(bench, "_get_client", new_callable=AsyncMock, return_value=mock_client):
            ok, latency = await bench.test("test/model:free")

        assert ok is True
        assert isinstance(latency, float)

    @pytest.mark.asyncio
    async def test_test_http_error(self, bench: ModelBenchmark) -> None:
        mock_client = MagicMock()
        mock_client.post = AsyncMock()
        mock_client.post.return_value.status_code = 429

        with patch.object(bench, "_get_client", new_callable=AsyncMock, return_value=mock_client):
            ok, latency = await bench.test("test/model:free")

        assert ok is False
        assert isinstance(latency, float)

    @pytest.mark.asyncio
    async def test_test_timeout(self, bench: ModelBenchmark) -> None:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        with patch.object(bench, "_get_client", new_callable=AsyncMock, return_value=mock_client):
            ok, latency = await bench.test("test/model:free")

        assert ok is False
        assert isinstance(latency, float)

    @pytest.mark.asyncio
    async def test_close(self, bench: ModelBenchmark) -> None:
        mock_client = MagicMock()
        mock_client.is_closed = False
        mock_client.aclose = AsyncMock()
        bench._client = mock_client

        await bench.close()
        mock_client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_client_reuses(self, bench: ModelBenchmark) -> None:
        mock_client = MagicMock()
        mock_client.is_closed = False
        bench._client = mock_client

        client = await bench._get_client()

        assert client is mock_client

    @pytest.mark.asyncio
    async def test_benchmark_skip_logs(self, bench: ModelBenchmark) -> None:
        mock_client = MagicMock()
        mock_client.post = AsyncMock()
        mock_client.post.return_value.status_code = 500

        with patch.object(bench, "_get_client", new_callable=AsyncMock, return_value=mock_client):
            ok, latency = await bench.test("test/model:free")

        assert ok is False
        assert isinstance(latency, float)


class TestSyncSnapshot:
    def test_create_snapshot(self) -> None:
        snap = SyncSnapshot(
            models_found=10,
            models_new=3,
            models_updated=5,
            models_removed=2,
            duration_ms=1500,
            error=None,
            source="test",
        )
        assert snap.models_found == 10
        assert snap.models_new == 3
        assert snap.error is None
        assert snap.source == "test"

    def test_snapshot_defaults(self) -> None:
        snap = SyncSnapshot()
        assert snap.models_found == 0
        assert snap.models_new == 0
        assert snap.error is None


class TestModelDiscoveryEngine:
    @pytest.mark.asyncio
    async def test_sync_no_models(self, engine: ModelDiscoveryEngine) -> None:
        with patch.object(engine, "_fetch_free_models", new_callable=AsyncMock, return_value=[]):
            with patch.object(engine, "_save_snapshot", new_callable=AsyncMock):
                snapshot = await engine.sync(source="test")

        assert snapshot.models_found == 0
        assert snapshot.error == "No free models returned by API"

    @pytest.mark.asyncio
    async def test_sync_with_models(self, engine: ModelDiscoveryEngine) -> None:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        free_models = [
            {
                "id": "test/free-model:free",
                "name": "Free Model",
                "pricing": {"prompt": "0", "completion": "0"},
                "context_length": 8192,
                "top_provider": {"max_completion_tokens": 4096},
            }
        ]

        with patch.object(
            engine, "_fetch_free_models", new_callable=AsyncMock, return_value=free_models
        ):
            with patch.object(
                engine, "_get_existing_ids", new_callable=AsyncMock, return_value=set()
            ):
                with patch.object(engine, "_upsert_model", new_callable=AsyncMock):
                    with patch.object(engine, "_save_snapshot", new_callable=AsyncMock):
                        snapshot = await engine.sync(source="test")

        assert snapshot.models_found == 1
        assert snapshot.models_new == 1

    @pytest.mark.asyncio
    async def test_sync_with_benchmark(self, mock_db: MagicMock) -> None:
        engine = ModelDiscoveryEngine(db_session=mock_db, run_benchmark=True)
        free_models = [
            {
                "id": "test/model:free",
                "name": "Test",
                "pricing": {"prompt": "0", "completion": "0"},
                "context_length": 8192,
                "top_provider": {"max_completion_tokens": 4096},
            }
        ]

        with patch.object(
            engine, "_fetch_free_models", new_callable=AsyncMock, return_value=free_models
        ):
            with patch.object(
                engine, "_get_existing_ids", new_callable=AsyncMock, return_value=set()
            ):
                with patch.object(
                    engine, "_benchmark_batch", new_callable=AsyncMock, return_value=[]
                ):
                    with patch.object(engine, "_save_snapshot", new_callable=AsyncMock):
                        snapshot = await engine.sync(source="test")

        assert snapshot.models_found == 1

    @pytest.mark.asyncio
    async def test_get_existing_ids(self, engine: ModelDiscoveryEngine) -> None:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("test/model:free",)]
        engine._db.execute = AsyncMock(return_value=mock_result)

        ids = await engine._get_existing_ids()
        assert ids == {"test/model:free"}

    @pytest.mark.asyncio
    async def test_fetch_free_models(self, engine: ModelDiscoveryEngine) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(
            return_value={
                "data": [{"id": "test/model:free", "pricing": {"prompt": "0", "completion": "0"}}]
            }
        )

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await engine._fetch_free_models()
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_fetch_free_models_api_error(self, engine: ModelDiscoveryEngine) -> None:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "500", request=MagicMock(), response=MagicMock(status_code=500)
            )
        )

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await engine._fetch_free_models()

    @pytest.mark.asyncio
    async def test_benchmark_batch(
        self, mock_db: MagicMock, classifier: ModelAutoClassifier
    ) -> None:
        engine = ModelDiscoveryEngine(db_session=mock_db, run_benchmark=True)
        model = classifier.classify(
            {
                "id": "test/model:free",
                "name": "Test",
                "pricing": {"prompt": "0", "completion": "0"},
                "context_length": 8192,
                "top_provider": {"max_completion_tokens": 4096},
            }
        )

        mock_bench = MagicMock()
        mock_bench.test = AsyncMock(return_value=(True, 500.0))
        engine._benchmark = mock_bench

        result = await engine._benchmark_batch([model])
        assert len(result) == 1
        assert result[0].raw_metadata["_benchmark"]["latency_ms"] == 500.0

    @pytest.mark.asyncio
    async def test_upsert_model_new(
        self, engine: ModelDiscoveryEngine, classifier: ModelAutoClassifier
    ) -> None:
        model = classifier.classify(
            {
                "id": "test/model:free",
                "name": "Test",
                "pricing": {"prompt": "0", "completion": "0"},
                "context_length": 8192,
                "top_provider": {"max_completion_tokens": 4096},
            }
        )
        engine._db.execute = AsyncMock(return_value=MagicMock())
        engine._db.commit = AsyncMock()

        await engine._upsert_model(model, is_new=True)

        engine._db.execute.assert_awaited()
        engine._db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_upsert_model_existing(
        self, engine: ModelDiscoveryEngine, classifier: ModelAutoClassifier
    ) -> None:
        model = classifier.classify(
            {
                "id": "test/model:free",
                "name": "Test",
                "pricing": {"prompt": "0", "completion": "0"},
                "context_length": 8192,
                "top_provider": {"max_completion_tokens": 4096},
            }
        )
        engine._db.execute = AsyncMock(return_value=MagicMock())
        engine._db.commit = AsyncMock()

        await engine._upsert_model(model, is_new=False)

        engine._db.execute.assert_awaited()
        engine._db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_disable_stale_model(self, engine: ModelDiscoveryEngine) -> None:
        engine._db.execute = AsyncMock(return_value=MagicMock())
        engine._db.commit = AsyncMock()

        await engine._disable_stale_model("stale/model:free")

        engine._db.execute.assert_awaited_once()
        engine._db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sync_with_classification_error(self, engine: ModelDiscoveryEngine) -> None:
        # Pass a model that breaks classifier by patching classify to raise
        bad_model = {
            "id": "test/bad:free",
            "name": "Bad",
            "pricing": {"prompt": "0", "completion": "0"},
            "context_length": 4096,
            "top_provider": {},
        }
        good_model = {
            "id": "test/good:free",
            "name": "Good",
            "pricing": {"prompt": "0", "completion": "0"},
            "context_length": 4096,
            "top_provider": {},
        }

        original_classifier = engine._classifier

        def _bad_classify(model: dict) -> dict:
            if model.get("id") == "test/bad:free":
                raise ValueError("classification failed")
            return original_classifier.classify(model)

        engine._classifier.classify = _bad_classify  # type: ignore[assignment]

        with patch.object(
            engine,
            "_fetch_free_models",
            new_callable=AsyncMock,
            return_value=[bad_model, good_model],
        ):
            with patch.object(
                engine, "_get_existing_ids", new_callable=AsyncMock, return_value=set()
            ):
                with patch.object(engine, "_upsert_model", new_callable=AsyncMock):
                    with patch.object(engine, "_save_snapshot", new_callable=AsyncMock):
                        snapshot = await engine.sync(source="test")

        assert snapshot.models_found == 2

    @pytest.mark.asyncio
    async def test_sync_with_exception(self, engine: ModelDiscoveryEngine) -> None:
        with patch.object(engine, "_fetch_free_models", side_effect=ValueError("network error")):
            with patch.object(engine, "_save_snapshot", new_callable=AsyncMock):
                snapshot = await engine.sync(source="test")

        assert snapshot.error is not None
        assert "network error" in snapshot.error

    @pytest.mark.asyncio
    async def test_sync_updates_existing(self, engine: ModelDiscoveryEngine) -> None:
        free_models = [
            {
                "id": "test/model:free",
                "name": "Updated Model",
                "pricing": {"prompt": "0", "completion": "0"},
                "context_length": 8192,
                "top_provider": {},
            }
        ]

        with patch.object(
            engine, "_fetch_free_models", new_callable=AsyncMock, return_value=free_models
        ):
            with patch.object(
                engine,
                "_get_existing_ids",
                new_callable=AsyncMock,
                return_value={"test/model:free"},
            ):
                with patch.object(engine, "_upsert_model", new_callable=AsyncMock):
                    with patch.object(engine, "_save_snapshot", new_callable=AsyncMock):
                        snapshot = await engine.sync(source="test")

        assert snapshot.models_updated == 1
        assert snapshot.models_new == 0

    @pytest.mark.asyncio
    async def test_sync_with_stale_models(self, engine: ModelDiscoveryEngine) -> None:
        free_models = [
            {
                "id": "test/model:free",
                "name": "Test",
                "pricing": {"prompt": "0", "completion": "0"},
                "context_length": 8192,
                "top_provider": {"max_completion_tokens": 4096},
            }
        ]

        with patch.object(
            engine, "_fetch_free_models", new_callable=AsyncMock, return_value=free_models
        ):
            with patch.object(
                engine,
                "_get_existing_ids",
                new_callable=AsyncMock,
                return_value={"stale/model:free"},
            ):
                with patch.object(engine, "_upsert_model", new_callable=AsyncMock):
                    with patch.object(
                        engine, "_disable_stale_model", new_callable=AsyncMock
                    ) as mock_disable:
                        with patch.object(engine, "_save_snapshot", new_callable=AsyncMock):
                            snapshot = await engine.sync(source="test")

        assert snapshot.models_removed == 1
        mock_disable.assert_awaited_once_with("stale/model:free")

    @pytest.mark.asyncio
    async def test_benchmark_batch_skip_on_fail(
        self, mock_db: MagicMock, classifier: ModelAutoClassifier
    ) -> None:
        engine = ModelDiscoveryEngine(db_session=mock_db, run_benchmark=True)
        model = classifier.classify(
            {
                "id": "test/model:free",
                "name": "Test",
                "pricing": {"prompt": "0", "completion": "0"},
                "context_length": 8192,
                "top_provider": {"max_completion_tokens": 4096},
            }
        )

        mock_bench = MagicMock()
        mock_bench.test = AsyncMock(return_value=(False, 60000.0))
        engine._benchmark = mock_bench

        result = await engine._benchmark_batch([model])
        assert len(result) == 0
        snapshot = SyncSnapshot(models_found=5, source="test")
        engine._db.execute = AsyncMock(return_value=MagicMock())
        engine._db.commit = AsyncMock()

        await engine._save_snapshot(snapshot)

        engine._db.execute.assert_awaited_once()
        engine._db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_client_creates_new(self) -> None:
        from app.utils.model_discovery import ModelBenchmark

        bench = ModelBenchmark()
        assert bench._client is None

        mock_client = MagicMock()
        mock_client.is_closed = False

        with patch("httpx.AsyncClient", return_value=mock_client):
            client = await bench._get_client()

        assert client is not None
