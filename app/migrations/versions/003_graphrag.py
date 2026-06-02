"""graphrag — knowledge graph storage for GraphRAG

Revision ID: 003
Revises: 002
Create Date: 2026-06-02
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "graph_entities",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", sa.String(64), nullable=False, index=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_graph_entities_workspace_name",
        "graph_entities",
        ["workspace_id", "name"],
        unique=True,
    )

    op.create_table(
        "graph_edges",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", sa.String(64), nullable=False, index=True),
        sa.Column("source_entity_id", UUID(), nullable=False),
        sa.Column("target_entity_id", UUID(), nullable=False),
        sa.Column("relation", sa.String(128), nullable=False),
        sa.Column("weight", sa.Float(), nullable=True, server_default=sa.text("1.0")),
        sa.Column("session_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["source_entity_id"],
            ["graph_entities.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_entity_id"],
            ["graph_entities.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_graph_edges_workspace", "graph_edges", ["workspace_id", "relation"])


def downgrade() -> None:
    op.drop_table("graph_edges")
    op.drop_table("graph_entities")
