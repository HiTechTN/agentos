from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from app.memory.vector_store import VectorStore, get_vector_store


class TestVectorStoreJsonFallback:
    @pytest.fixture
    def vs(self):
        instance = VectorStore()
        instance._use_json_fallback = True
        return instance

    @pytest.mark.asyncio
    async def test_store_json_fallback(self, vs):
        mock_embedding = [0.1, 0.2, 0.3]
        with (
            patch.object(vs._embedding_client, "embed", AsyncMock(return_value=mock_embedding)),
            patch("os.makedirs"),
            patch("os.path.exists", return_value=False),
            patch("builtins.open", mock_open()),
            patch("app.memory.vector_store.json.dump"),
        ):
            entry_id = await vs.store("proj-1", "hello world", {"source": "test"})
            assert isinstance(entry_id, str)
            assert len(entry_id) > 0

    @pytest.mark.asyncio
    async def test_store_json_fallback_no_metadata(self, vs):
        mock_embedding = [0.1, 0.2, 0.3]
        with (
            patch.object(vs._embedding_client, "embed", AsyncMock(return_value=mock_embedding)),
            patch("os.makedirs"),
            patch("os.path.exists", return_value=False),
            patch("builtins.open", mock_open()),
            patch("app.memory.vector_store.json.dump"),
        ):
            entry_id = await vs.store("proj-1", "hello world")
            assert isinstance(entry_id, str)

    @pytest.mark.asyncio
    async def test_search_json_fallback(self, vs):
        mock_embedding = [0.1, 0.2, 0.3]
        mock_data = [
            {"id": "1", "project_id": "proj-1", "content": "hello", "metadata": {}, "embedding": [0.1]},  # noqa: E501
            {"id": "2", "project_id": "other", "content": "other", "metadata": {}, "embedding": [0.2]},  # noqa: E501
        ]
        with (
            patch.object(vs._embedding_client, "embed", AsyncMock(return_value=mock_embedding)),
            patch("os.path.exists", return_value=True),
            patch("builtins.open", mock_open()),
            patch("app.memory.vector_store.json.load", return_value=mock_data),
        ):
            results = await vs.search("proj-1", "hello", top_k=5)
            assert len(results) == 1
            assert results[0]["id"] == "1"
            assert results[0]["content"] == "hello"
            assert results[0]["similarity"] == 0.0

    @pytest.mark.asyncio
    async def test_search_json_fallback_no_file(self, vs):
        mock_embedding = [0.1, 0.2, 0.3]
        with (
            patch.object(vs._embedding_client, "embed", AsyncMock(return_value=mock_embedding)),
            patch("os.path.exists", return_value=False),
        ):
            results = await vs.search("proj-1", "hello", top_k=5)
            assert results == []

    @pytest.mark.asyncio
    async def test_delete_json_fallback(self, vs):
        result = await vs.delete("id-1")
        assert result is False


class TestVectorStorePostgres:
    @pytest.fixture
    def vs(self):
        return VectorStore()

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def mock_factory(self, mock_session):
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_session)
        cm.__aexit__ = AsyncMock()
        factory = MagicMock(return_value=cm)
        return factory

    @pytest.mark.asyncio
    async def test_store_pg(self, vs, mock_factory, mock_session):
        mock_embedding = [0.1, 0.2, 0.3]
        with (
            patch.object(vs._embedding_client, "embed", AsyncMock(return_value=mock_embedding)),
            patch.object(vs, "_init_db", AsyncMock()),
            patch.object(vs, "_session_factory", mock_factory),
        ):
            entry_id = await vs.store("proj-1", "hello world", {"source": "test"})
            assert isinstance(entry_id, str)
            assert len(entry_id) > 0
            mock_session.execute.assert_called_once()
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_pg(self, vs, mock_factory):
        mock_embedding = [0.1, 0.2, 0.3]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("id-1", "hello world", '{"source":"test"}', 0.95)]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_session)
        cm.__aexit__ = AsyncMock()
        factory = MagicMock(return_value=cm)

        with (
            patch.object(vs._embedding_client, "embed", AsyncMock(return_value=mock_embedding)),
            patch.object(vs, "_init_db", AsyncMock()),
            patch.object(vs, "_session_factory", factory),
        ):
            results = await vs.search("proj-1", "hello", top_k=5)
            assert len(results) == 1
            assert results[0]["id"] == "id-1"
            assert results[0]["content"] == "hello world"
            assert results[0]["similarity"] == 0.95

    @pytest.mark.asyncio
    async def test_delete_pg(self, vs, mock_factory):
        mock_result = MagicMock()
        mock_result.rowcount = 1

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_session)
        cm.__aexit__ = AsyncMock()
        factory = MagicMock(return_value=cm)

        with (
            patch.object(vs, "_init_db", AsyncMock()),
            patch.object(vs, "_session_factory", factory),
        ):
            result = await vs.delete("id-1")
            assert result is True

    @pytest.mark.asyncio
    async def test_delete_pg_not_found(self, vs, mock_factory):
        mock_result = MagicMock()
        mock_result.rowcount = 0

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_session)
        cm.__aexit__ = AsyncMock()
        factory = MagicMock(return_value=cm)

        with (
            patch.object(vs, "_init_db", AsyncMock()),
            patch.object(vs, "_session_factory", factory),
        ):
            result = await vs.delete("nonexistent")
            assert result is False

    @pytest.mark.asyncio
    async def test_search_pg_empty(self, vs, mock_factory):
        mock_embedding = [0.1, 0.2, 0.3]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_session)
        cm.__aexit__ = AsyncMock()
        factory = MagicMock(return_value=cm)

        with (
            patch.object(vs._embedding_client, "embed", AsyncMock(return_value=mock_embedding)),
            patch.object(vs, "_init_db", AsyncMock()),
            patch.object(vs, "_session_factory", factory),
        ):
            results = await vs.search("proj-1", "hello", top_k=5)
            assert results == []


class TestVectorStoreSingleton:
    @pytest.mark.asyncio
    async def test_get_vector_store_singleton(self):
        import app.memory.vector_store as vs_module

        with patch.object(vs_module, "_vector_store", None):
            v1 = get_vector_store()
            v2 = get_vector_store()
            assert v1 is v2
