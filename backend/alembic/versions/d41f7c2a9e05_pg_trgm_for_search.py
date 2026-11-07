"""pg_trgm для поиска с учётом морфологии

Revision ID: d41f7c2a9e05
Revises: bc1ab3c10b49
Create Date: 2026-11-07

FTS (russian) ловит общие словоформы, но не приставочные варианты
(«приготовленное» → «приготовлен», «готовлю» → «готовл») — их добирает
триграммное word_similarity. GIN-индекс по lower(text) — под операторы
pg_trgm (%, <%) на будущий рост объёма; текущие запросы с
word_similarity(...) > порог идут seq scan — при объёмах чата это дёшево.
"""

import sqlalchemy as sa
from alembic import op

revision = "d41f7c2a9e05"
down_revision = "bc1ab3c10b49"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX ix_messages_lower_text_trgm ON messages USING gin (lower(text) gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_messages_lower_text_trgm")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
