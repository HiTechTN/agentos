"""model_registry — auto-discovered free LLM models catalog

Revision ID: 004
Revises: 003
Create Date: 2026-06-02
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "discovered_models",
        sa.Column("id", sa.String(256), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("provider", sa.String(128), nullable=False, index=True),
        sa.Column("context_window", sa.Integer(), nullable=False, server_default="4096"),
        sa.Column("supports_tools", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("supports_vision", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("supports_reasoning", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("supports_json_mode", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("max_output_tokens", sa.Integer(), nullable=True),
        sa.Column("work_types", JSONB(), nullable=False, server_default="[]"),  # type: ignore[no-untyped-call]
        sa.Column(
            "primary_work_type", sa.String(64), nullable=False, server_default="general", index=True
        ),
        sa.Column("is_free", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("pricing_prompt", sa.String(32), nullable=False, server_default="0"),
        sa.Column("pricing_completion", sa.String(32), nullable=False, server_default="0"),
        sa.Column("req_per_min", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("req_per_day", sa.Integer(), nullable=False, server_default="200"),
        sa.Column("avg_latency_ms", sa.Float(), nullable=True),
        sa.Column("success_rate", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("quality_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("total_requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true", index=True),
        sa.Column("is_benchmarked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("disabled_reason", sa.String(256), nullable=True),
        sa.Column("rotation_weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_rate_limited_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_metadata", JSONB(), nullable=True),  # type: ignore[no-untyped-call]
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index(
        "ix_models_work_type_active", "discovered_models", ["primary_work_type", "is_active"]
    )
    op.create_index("ix_models_quality", "discovered_models", ["quality_score", "success_rate"])

    op.create_table(
        "model_rotation_log",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("model_id", sa.String(256), nullable=False, index=True),
        sa.Column("work_type", sa.String(64), nullable=False, index=True),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_code", sa.String(32), nullable=True),
        sa.Column("rotated_to", sa.String(256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "discovery_snapshots",
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


def downgrade() -> None:
    op.drop_table("discovery_snapshots")
    op.drop_table("model_rotation_log")
    op.drop_table("discovered_models")
