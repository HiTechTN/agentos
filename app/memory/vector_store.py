import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config.settings import get_settings
from app.utils.api_clients import EmbeddingClient
from app.utils.logging import get_logger

logger = get_logger("vector_store")


class VectorStore:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._engine: Any = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self._embedding_client = EmbeddingClient()
        self._use_json_fallback = False

    async def _init_db(self) -> None:
        if self._engine is not None:
            return
        try:
            self._engine = create_async_engine(self.settings.resolved_database_url, echo=False)
            self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)
            async with self._engine.begin() as conn:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
            logger.log_action("vector_store", "db_init", "connected", details={"db": "postgres"})
        except Exception as e:
            logger.log_warn(
                "vector_store", "db_init", f"PostgreSQL unavailable, using JSON fallback: {e}"
            )
            self._use_json_fallback = True

    async def store(
        self, project_id: str, content: str, metadata: dict[str, Any] | None = None
    ) -> str:
        entry_id = str(uuid.uuid4())
        embedding = await self._embedding_client.embed(content)

        if self._use_json_fallback:
            return await self._store_json(entry_id, project_id, content, metadata, embedding)

        try:
            await self._init_db()
            async with self._session_factory() as session:  # type: ignore[misc]
                stmt = text("""
                    INSERT INTO embeddings
                        (id, project_id, content, metadata, embedding, created_at)
                    VALUES
                        (:id, :project_id, :content, :metadata, :embedding, :created_at)
                """)
                await session.execute(
                    stmt,
                    {
                        "id": entry_id,
                        "project_id": project_id,
                        "content": content,
                        "metadata": json.dumps(metadata or {}),
                        "embedding": str(embedding),
                        "created_at": datetime.now(UTC),
                    },
                )
                await session.commit()
            return entry_id
        except Exception as e:
            logger.log_warn("vector_store", "store", f"DB write failed, JSON fallback: {e}")
            return await self._store_json(entry_id, project_id, content, metadata, embedding)

    async def search(self, project_id: str, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        embedding = await self._embedding_client.embed(query)

        if self._use_json_fallback:
            return self._search_json(project_id, query, top_k)

        try:
            await self._init_db()
            async with self._session_factory() as session:  # type: ignore[misc]
                stmt = text("""
                    SELECT id, content, metadata,
                           1 - (embedding <=> :embedding::vector) AS similarity
                    FROM embeddings
                    WHERE project_id = :project_id
                    ORDER BY similarity DESC
                    LIMIT :top_k
                """)
                result = await session.execute(
                    stmt,
                    {
                        "embedding": str(embedding),
                        "project_id": project_id,
                        "top_k": top_k,
                    },
                )
                rows = result.fetchall()
                return [
                    {"id": r[0], "content": r[1], "metadata": r[2], "similarity": float(r[3])}
                    for r in rows
                ]
        except Exception as e:
            logger.log_warn("vector_store", "search", f"DB search failed, JSON fallback: {e}")
            return self._search_json(project_id, query, top_k)

    async def delete(self, entry_id: str) -> bool:
        if self._use_json_fallback:
            return False
        try:
            await self._init_db()
            async with self._session_factory() as session:  # type: ignore[misc]
                stmt = text("DELETE FROM embeddings WHERE id = :id")
                result = await session.execute(stmt, {"id": entry_id})
                await session.commit()
                rc: int = result.rowcount  # type: ignore[union-attr]
                return rc > 0
        except Exception:
            return False

    def _json_fallback_path(self) -> str:
        import os

        return os.path.join(self.settings.project_id, "memory_fallback.json")

    async def _store_json(
        self,
        entry_id: str,
        project_id: str,
        content: str,
        metadata: dict[str, Any] | None,
        embedding: list[float],
    ) -> str:
        import os

        path = self._json_fallback_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        entries = []
        if os.path.exists(path):
            with open(path) as f:
                entries = json.load(f)
        entries.append(
            {
                "id": entry_id,
                "project_id": project_id,
                "content": content,
                "metadata": metadata or {},
                "embedding": embedding,
                "created_at": datetime.now(UTC).isoformat(),
            }
        )
        with open(path, "w") as f:
            json.dump(entries, f, default=str)
        return entry_id

    def _search_json(self, project_id: str, query: str, top_k: int) -> list[dict[str, Any]]:
        import os

        path = self._json_fallback_path()
        if not os.path.exists(path):
            return []
        with open(path) as f:
            entries = json.load(f)
        filtered = [e for e in entries if e.get("project_id") == project_id]
        return [
            {
                "id": e["id"],
                "content": e["content"],
                "metadata": e.get("metadata", {}),
                "similarity": 0.0,
            }
            for e in filtered[:top_k]
        ]


_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
