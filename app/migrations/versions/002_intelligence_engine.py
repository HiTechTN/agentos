"""intelligence_engine — episodic memory, skills, knowledge base

Revision ID: 002
Revises: 7e3f1a2b5c0d
Create Date: 2026-05-31
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "002"
down_revision: str | None = "7e3f1a2b5c0d"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "episodic_memories",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", sa.String(64), nullable=False, index=True),
        sa.Column("session_id", UUID(), nullable=True, index=True),
        sa.Column("task_type", sa.String(64), nullable=False, index=True),
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
        sa.Column("context_tags", sa.JSON(), nullable=True),
        sa.Column("embedding", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_episodic_task_outcome", "episodic_memories", ["task_type", "outcome"])
    op.create_index(
        "ix_episodic_workspace_created", "episodic_memories", ["workspace_id", "created_at"]
    )

    op.create_table(
        "skills",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", sa.String(64), nullable=False, index=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("category", sa.String(64), nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("trigger_patterns", sa.JSON(), nullable=False),
        sa.Column("procedure", sa.Text(), nullable=False),
        sa.Column("example_prompt", sa.Text(), nullable=True),
        sa.Column("example_output", sa.Text(), nullable=True),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("auto_discovered", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("source_memory_ids", sa.JSON(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("embedding_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "slug", name="uq_skill_slug"),
    )
    op.create_index("ix_skills_category_confidence", "skills", ["category", "confidence_score"])

    op.create_table(
        "knowledge_entries",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", sa.String(64), nullable=False, index=True),
        sa.Column("kind", sa.String(64), nullable=False, index=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("embedding_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    op.create_table(
        "agent_evolutions",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", sa.String(64), nullable=False, index=True),
        sa.Column("agent_name", sa.String(64), nullable=False, index=True),
        sa.Column("evolution_type", sa.String(64), nullable=False),
        sa.Column("trigger_reason", sa.Text(), nullable=False),
        sa.Column("before_state", sa.JSON(), nullable=True),
        sa.Column("after_state", sa.JSON(), nullable=False),
        sa.Column("performance_delta", sa.Float(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
    )

    op.create_table(
        "reflection_reports",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", sa.String(64), nullable=False, index=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tasks_analyzed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_skills_discovered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("knowledge_entries_added", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_quality_score", sa.Float(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("top_patterns", sa.JSON(), nullable=True),
        sa.Column("recommendations", sa.JSON(), nullable=True),
        sa.Column("model_performance", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("reflection_reports")
    op.drop_table("agent_evolutions")
    op.drop_table("knowledge_entries")
    op.drop_table("skills")
    op.drop_table("episodic_memories")
