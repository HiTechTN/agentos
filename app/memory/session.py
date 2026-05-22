import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config.settings import get_settings
from app.utils.logging import get_logger

logger = get_logger("session")


class SessionManager:
    def __init__(self):
        self.settings = get_settings()
        self._engine = None
        self._session_factory = None
        self._use_json_fallback = False
        self._sessions: dict[str, dict] = {}

    async def _init_db(self):
        if self._engine is not None:
            return
        try:
            self._engine = create_async_engine(self.settings.resolved_database_url, echo=False)
            self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)
            logger.log_action("session", "db_init", "connected")
        except Exception as e:
            logger.log_warn(
                "session", "db_init", f"PostgreSQL unavailable, using JSON fallback: {e}"
            )
            self._use_json_fallback = True

    async def create(self, project_id: str, workflow_id: str = "") -> str:
        session_id = str(uuid.uuid4())
        session_data = {
            "id": session_id,
            "project_id": project_id,
            "workflow_id": workflow_id or f"wf-{session_id[:8]}",
            "status": "pending",
            "context": {},
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }

        if self._use_json_fallback:
            self._sessions[session_id] = session_data
            return session_id

        try:
            await self._init_db()
            async with self._session_factory() as session:
                stmt = text("""
                    INSERT INTO sessions (id, project_id, workflow_id, status, context, created_at, updated_at)
                    VALUES (:id, :project_id, :workflow_id, :status, :context, :created_at, :updated_at)
                """)
                await session.execute(
                    stmt,
                    {
                        "id": session_id,
                        "project_id": project_id,
                        "workflow_id": session_data["workflow_id"],
                        "status": session_data["status"],
                        "context": json.dumps(session_data["context"]),
                        "created_at": session_data["created_at"],
                        "updated_at": session_data["updated_at"],
                    },
                )
                await session.commit()
        except Exception as e:
            logger.log_warn("session", "create", f"DB failed, memory fallback: {e}")
            self._sessions[session_id] = session_data

        return session_id

    async def update(
        self, session_id: str, context: dict | None = None, status: str | None = None
    ) -> bool:
        now = datetime.now(UTC).isoformat()

        if self._use_json_fallback or session_id in self._sessions:
            if session_id not in self._sessions:
                return False
            if context:
                self._sessions[session_id]["context"] = context
            if status:
                self._sessions[session_id]["status"] = status
            self._sessions[session_id]["updated_at"] = now
            return True

        try:
            await self._init_db()
            async with self._session_factory() as session:
                updates = ["updated_at = :updated_at"]
                params = {"id": session_id, "updated_at": now}
                if context is not None:
                    updates.append("context = :context")
                    params["context"] = json.dumps(context)
                if status is not None:
                    updates.append("status = :status")
                    params["status"] = status
                stmt = text(f"UPDATE sessions SET {', '.join(updates)} WHERE id = :id")
                result = await session.execute(stmt, params)
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.log_warn("session", "update", f"DB update failed: {e}")
            return False

    async def get(self, session_id: str) -> dict | None:
        if self._use_json_fallback or session_id in self._sessions:
            return self._sessions.get(session_id)

        try:
            await self._init_db()
            async with self._session_factory() as session:
                stmt = text("SELECT * FROM sessions WHERE id = :id")
                result = await session.execute(stmt, {"id": session_id})
                row = result.fetchone()
                if row:
                    return {
                        "id": row[0],
                        "project_id": row[1],
                        "workflow_id": row[2],
                        "status": row[3],
                        "context": json.loads(row[4]) if isinstance(row[4], str) else row[4],
                        "created_at": row[5].isoformat()
                        if hasattr(row[5], "isoformat")
                        else row[5],
                        "updated_at": row[6].isoformat()
                        if hasattr(row[6], "isoformat")
                        else row[6],
                    }
                return None
        except Exception as e:
            logger.log_warn("session", "get", f"DB get failed: {e}")
            return self._sessions.get(session_id)


_session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
