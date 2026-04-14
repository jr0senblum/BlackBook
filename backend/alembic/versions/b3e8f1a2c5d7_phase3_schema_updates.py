"""Phase 3 schema updates: functional_areas notes+updated_at, inferred_facts product category.

Revision ID: b3e8f1a2c5d7
Revises: 454cf50473b8
Create Date: 2026-04-14

Changes:
  - Add 'notes' column (text, nullable) to functional_areas
  - Add 'updated_at' column (timestamptz, NOT NULL, server_default now()) to functional_areas
  - Replace inferred_facts.category CHECK constraint to include 'product'
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b3e8f1a2c5d7"
down_revision = "454cf50473b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- functional_areas: add notes and updated_at --
    op.add_column("functional_areas", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column(
        "functional_areas",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # -- inferred_facts: replace category CHECK to include 'product' --
    op.drop_constraint("ck_inferred_facts_category", "inferred_facts", type_="check")
    op.create_check_constraint(
        "ck_inferred_facts_category",
        "inferred_facts",
        "category IN ("
        "'functional-area', 'person', 'relationship', "
        "'technology', 'process', 'product', "
        "'cgkra-cs', 'cgkra-gw', 'cgkra-kp', 'cgkra-rm', 'cgkra-aop', "
        "'swot-s', 'swot-w', 'swot-o', 'swot-th', "
        "'action-item', 'other'"
        ")",
    )


def downgrade() -> None:
    # -- Revert inferred_facts category CHECK --
    op.drop_constraint("ck_inferred_facts_category", "inferred_facts", type_="check")
    op.create_check_constraint(
        "ck_inferred_facts_category",
        "inferred_facts",
        "category IN ("
        "'functional-area', 'person', 'relationship', "
        "'technology', 'process', "
        "'cgkra-cs', 'cgkra-gw', 'cgkra-kp', 'cgkra-rm', 'cgkra-aop', "
        "'swot-s', 'swot-w', 'swot-o', 'swot-th', "
        "'action-item', 'other'"
        ")",
    )

    # -- Revert functional_areas columns --
    op.drop_column("functional_areas", "updated_at")
    op.drop_column("functional_areas", "notes")
