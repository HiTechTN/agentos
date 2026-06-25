"""Alembic environment configuration for AgentOS."""

import asyncio
from logging.config import fileConfig

import sqlalchemy as sa
from alembic import context
from pgvector.sqlalchemy import Vector
from sqlalchemy import MetaData, pool
from sqlalchemy.dialects.postgresql import JSON, JSONB, UUID

from app.config.settings import get_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Store DB URL for later use (keep async scheme)
settings = get_settings()
db_url = settings.resolved_database_url

# ── Schema definition ────────────────────────────────────────────────────────
# Mirrors all tables created by migrations so `alembic check` can detect drift.
# Keep in sync with migration files in versions/.

metadata = MetaData()

# --- baseline_v5 (72df454c94ee) ---

sa.Table(
    "projects",
    metadata,
    sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),
    sa.Column(
        "state",
        JSONB(),  # type: ignore[no-untyped-call]
        nullable=True,
        server_default=sa.text("'{}'::jsonb"),
    ),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
)

sa.Table(
    "sessions",
    metadata,
    sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column(
        "project_id", UUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    ),
    sa.Column("workflow_id", sa.String(255), nullable=True),
    sa.Column("status", sa.String(50), nullable=True, server_default=sa.text("'pending'")),
    sa.Column(
        "context",
        JSONB(),  # type: ignore[no-untyped-call]
        nullable=True,
        server_default=sa.text("'{}'::jsonb"),
    ),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.Index("idx_sessions_project", "project_id"),
)

sa.Table(
    "embeddings",
    metadata,
    sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column(
        "project_id", UUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    ),
    sa.Column("content", sa.Text(), nullable=False),
    sa.Column(
        "metadata",
        JSONB(),  # type: ignore[no-untyped-call]
        nullable=True,
        server_default=sa.text("'{}'::jsonb"),
    ),
    sa.Column("embedding", Vector(768), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.Index("idx_embeddings_project", "project_id"),
)

sa.Table(
    "hitl_approvals",
    metadata,
    sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column(
        "session_id", UUID(), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True
    ),
    sa.Column("agent_name", sa.String(100), nullable=False),
    sa.Column("action", sa.String(255), nullable=False),
    sa.Column(
        "details",
        JSONB(),  # type: ignore[no-untyped-call]
        nullable=True,
        server_default=sa.text("'{}'::jsonb"),
    ),
    sa.Column("status", sa.String(50), nullable=True, server_default=sa.text("'pending'")),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
)

# --- users & social_accounts (7e3f1a2b5c0d) ---

sa.Table(
    "users",
    metadata,
    sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column("email", sa.String(255), nullable=False, unique=True),
    sa.Column("password_hash", sa.String(255), nullable=True),
    sa.Column("name", sa.String(255), nullable=True),
    sa.Column("avatar_url", sa.String(512), nullable=True),
    sa.Column("role", sa.String(50), nullable=False, server_default="user"),
    sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.Index("idx_users_email", "email"),
)

sa.Table(
    "social_accounts",
    metadata,
    sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column("user_id", UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    sa.Column("provider", sa.String(50), nullable=False),
    sa.Column("provider_user_id", sa.String(255), nullable=False),
    sa.Column("provider_email", sa.String(255), nullable=True),
    sa.Column("access_token", sa.Text(), nullable=True),
    sa.Column("refresh_token", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.Index("idx_social_accounts_provider", "provider", "provider_user_id"),
)

# --- intelligence engine (002) ---

sa.Table(
    "episodic_memories",
    metadata,
    sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column("workspace_id", sa.String(64), nullable=False),
    sa.Column("session_id", UUID(), nullable=True),
    sa.Column("task_type", sa.String(64), nullable=False),
    sa.Column("prompt_summary", sa.Text(), nullable=False),
    sa.Column("outcome", sa.String(32), nullable=False, server_default="unknown"),
    sa.Column("quality_score", sa.Float(), nullable=True),
    sa.Column("duration_ms", sa.Integer(), nullable=True),
    sa.Column("agent_used", sa.String(64), nullable=True),
    sa.Column("model_used", sa.String(128), nullable=True),
    sa.Column("work_type", sa.String(64), nullable=True),
    sa.Column("input_tokens", sa.Integer(), nullable=True),
    sa.Column("output_tokens", sa.Integer(), nullable=True),
    sa.Column("strategy_used", sa.Text(), nullable=True),
    sa.Column("what_worked", sa.Text(), nullable=True),
    sa.Column("what_failed", sa.Text(), nullable=True),
    sa.Column(
        "context_tags",
        JSONB(),  # type: ignore[no-untyped-call]
        nullable=True,
    ),
    sa.Column("embedding", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.Index("ix_episodic_memories_workspace_id", "workspace_id"),
    sa.Index("ix_episodic_memories_session_id", "session_id"),
    sa.Index("ix_episodic_memories_task_type", "task_type"),
    sa.Index("ix_episodic_task_outcome", "task_type", "outcome"),
    sa.Index("ix_episodic_workspace_created", "workspace_id", "created_at"),
)

sa.Table(
    "skills",
    metadata,
    sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column("workspace_id", sa.String(64), nullable=False),
    sa.Column("name", sa.String(128), nullable=False),
    sa.Column("slug", sa.String(128), nullable=False),
    sa.Column("category", sa.String(64), nullable=False),
    sa.Column("description", sa.Text(), nullable=False),
    sa.Column(
        "trigger_patterns",
        JSONB(),  # type: ignore[no-untyped-call]
        nullable=False,
    ),
    sa.Column("procedure", sa.Text(), nullable=False),
    sa.Column("example_prompt", sa.Text(), nullable=True),
    sa.Column("example_output", sa.Text(), nullable=True),
    sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0.5"),
    sa.Column("auto_discovered", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    sa.Column(
        "source_memory_ids",
        JSONB(),  # type: ignore[no-untyped-call]
        nullable=True,
    ),
    sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    sa.Column("embedding_json", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    sa.UniqueConstraint("workspace_id", "slug", name="uq_skill_slug"),
    sa.Index("ix_skills_workspace_id", "workspace_id"),
    sa.Index("ix_skills_category", "category"),
    sa.Index("ix_skills_category_confidence", "category", "confidence_score"),
)

sa.Table(
    "knowledge_entries",
    metadata,
    sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column("workspace_id", sa.String(64), nullable=False),
    sa.Column("kind", sa.String(64), nullable=False),
    sa.Column("title", sa.String(256), nullable=False),
    sa.Column("content", sa.Text(), nullable=False),
    sa.Column("source_type", sa.String(64), nullable=True),
    sa.Column("confidence", sa.Float(), nullable=False, server_default="0.7"),
    sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "tags",
        JSONB(),  # type: ignore[no-untyped-call]
        nullable=True,
    ),
    sa.Column("embedding_json", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    sa.Index("ix_knowledge_entries_workspace_id", "workspace_id"),
    sa.Index("ix_knowledge_entries_kind", "kind"),
)

sa.Table(
    "agent_evolutions",
    metadata,
    sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column("workspace_id", sa.String(64), nullable=False),
    sa.Column("agent_name", sa.String(64), nullable=False),
    sa.Column("evolution_type", sa.String(64), nullable=False),
    sa.Column("trigger_reason", sa.Text(), nullable=False),
    sa.Column(
        "before_state",
        JSONB(),  # type: ignore[no-untyped-call]
        nullable=True,
    ),
    sa.Column(
        "after_state",
        JSONB(),  # type: ignore[no-untyped-call]
        nullable=False,
    ),
    sa.Column("performance_delta", sa.Float(), nullable=True),
    sa.Column("applied_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
    sa.Index("ix_agent_evolutions_workspace_id", "workspace_id"),
    sa.Index("ix_agent_evolutions_agent_name", "agent_name"),
)

sa.Table(
    "reflection_reports",
    metadata,
    sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column("workspace_id", sa.String(64), nullable=False),
    sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
    sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
    sa.Column("tasks_analyzed", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("new_skills_discovered", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("knowledge_entries_added", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("avg_quality_score", sa.Float(), nullable=True),
    sa.Column("summary", sa.Text(), nullable=True),
    sa.Column(
        "top_patterns",
        JSONB(),  # type: ignore[no-untyped-call]
        nullable=True,
    ),
    sa.Column(
        "recommendations",
        JSONB(),  # type: ignore[no-untyped-call]
        nullable=True,
    ),
    sa.Column(
        "model_performance",
        JSONB(),  # type: ignore[no-untyped-call]
        nullable=True,
    ),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.Index("ix_reflection_reports_workspace_id", "workspace_id"),
)

# --- graphrag (003) ---

sa.Table(
    "graph_entities",
    metadata,
    sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column("workspace_id", sa.String(64), nullable=False),
    sa.Column("name", sa.String(256), nullable=False),
    sa.Column("entity_type", sa.String(64), nullable=True),
    sa.Column(
        "metadata_json",
        JSON(),  # type: ignore[no-untyped-call]
        nullable=True,
    ),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Index("ix_graph_entities_workspace_id", "workspace_id"),
    sa.Index("ix_graph_entities_workspace_name", "workspace_id", "name", unique=True),
)

sa.Table(
    "graph_edges",
    metadata,
    sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column("workspace_id", sa.String(64), nullable=False),
    sa.Column(
        "source_entity_id",
        UUID(),
        sa.ForeignKey("graph_entities.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "target_entity_id",
        UUID(),
        sa.ForeignKey("graph_entities.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("relation", sa.String(128), nullable=False),
    sa.Column("weight", sa.Float(), nullable=True, server_default=sa.text("1.0")),
    sa.Column("session_id", sa.String(64), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Index("ix_graph_edges_workspace_id", "workspace_id"),
    sa.Index("ix_graph_edges_workspace", "workspace_id", "relation"),
)

# --- model registry (004) ---

sa.Table(
    "discovered_models",
    metadata,
    sa.Column("id", sa.String(256), primary_key=True),
    sa.Column("name", sa.String(256), nullable=False),
    sa.Column("provider", sa.String(128), nullable=False),
    sa.Column("context_window", sa.Integer(), nullable=False, server_default="4096"),
    sa.Column("supports_tools", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    sa.Column("supports_vision", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    sa.Column("supports_reasoning", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    sa.Column("supports_json_mode", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    sa.Column("max_output_tokens", sa.Integer(), nullable=True),
    sa.Column(
        "work_types",
        JSONB(),  # type: ignore[no-untyped-call]
        nullable=False,
        server_default=sa.text("'[]'::jsonb"),
    ),
    sa.Column("primary_work_type", sa.String(64), nullable=False, server_default="general"),
    sa.Column("is_free", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    sa.Column("pricing_prompt", sa.String(32), nullable=False, server_default="0"),
    sa.Column("pricing_completion", sa.String(32), nullable=False, server_default="0"),
    sa.Column("req_per_min", sa.Integer(), nullable=False, server_default="20"),
    sa.Column("req_per_day", sa.Integer(), nullable=False, server_default="200"),
    sa.Column("avg_latency_ms", sa.Float(), nullable=True),
    sa.Column("success_rate", sa.Float(), nullable=False, server_default="1.0"),
    sa.Column("quality_score", sa.Float(), nullable=False, server_default="0.5"),
    sa.Column("total_requests", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("total_errors", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    sa.Column("is_benchmarked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    sa.Column("disabled_reason", sa.String(256), nullable=True),
    sa.Column("rotation_weight", sa.Float(), nullable=False, server_default="1.0"),
    sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("is_rate_limited_until", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "raw_metadata",
        JSONB(),  # type: ignore[no-untyped-call]
        nullable=True,
    ),
    sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.Column("last_checked_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    sa.Index("ix_discovered_models_provider", "provider"),
    sa.Index("ix_discovered_models_primary_work_type", "primary_work_type"),
    sa.Index("ix_discovered_models_is_active", "is_active"),
    sa.Index("ix_models_work_type_active", "primary_work_type", "is_active"),
    sa.Index("ix_models_quality", "quality_score", "success_rate"),
)

sa.Table(
    "model_rotation_log",
    metadata,
    sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column("model_id", sa.String(256), nullable=False),
    sa.Column("work_type", sa.String(64), nullable=False),
    sa.Column("reason", sa.String(64), nullable=False),
    sa.Column("latency_ms", sa.Integer(), nullable=True),
    sa.Column("success", sa.Boolean(), nullable=False),
    sa.Column("error_code", sa.String(32), nullable=True),
    sa.Column("rotated_to", sa.String(256), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.Index("ix_model_rotation_log_model_id", "model_id"),
    sa.Index("ix_model_rotation_log_work_type", "work_type"),
)

sa.Table(
    "discovery_snapshots",
    metadata,
    sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column("models_found", sa.Integer(), nullable=False),
    sa.Column("models_new", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("models_removed", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("models_updated", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("source", sa.String(64), nullable=False, server_default="scheduler"),
    sa.Column("duration_ms", sa.Integer(), nullable=True),
    sa.Column("error", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
)

target_metadata = metadata


def run_migrations_offline() -> None:
    url = db_url or "postgresql://localhost/agentos"
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    if not db_url:
        print("No database URL configured, running in offline mode")
        run_migrations_offline()
        return

    from sqlalchemy.ext.asyncio import create_async_engine

    async def do_run() -> None:
        connectable = create_async_engine(db_url, echo=False, poolclass=pool.NullPool)
        async with connectable.connect() as connection:
            await connection.run_sync(
                lambda sync_conn: context.configure(
                    connection=sync_conn,
                    target_metadata=target_metadata,
                )
            )
            async with connection.begin():
                await connection.run_sync(lambda _: context.run_migrations())
        await connectable.dispose()

    try:
        asyncio.run(do_run())
    except Exception as exc:
        import sys

        print(f"Database unavailable, running in offline mode: {exc}", file=sys.stderr)
        run_migrations_offline()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
