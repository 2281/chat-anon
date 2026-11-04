"""notifications kind and actor

Revision ID: 661dce435947
Revises: 9ce965e1f84d
Create Date: 2026-11-04 11:26:01.449656

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '661dce435947'
down_revision: Union[str, Sequence[str], None] = '9ce965e1f84d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('notifications', sa.Column('kind', sa.String(length=16), server_default='reply', nullable=False))
    op.add_column('notifications', sa.Column('actor_token', sa.Uuid(), nullable=True))
    op.create_foreign_key('fk_notifications_actor_token', 'notifications', 'participants', ['actor_token'], ['token'], ondelete='SET NULL')
    # бэкфилл: у существующих уведомлений-ответов актор — автор сообщения-ответа
    op.execute(
        "UPDATE notifications SET actor_token = messages.participant_token "
        "FROM messages WHERE notifications.message_id = messages.id"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_notifications_actor_token', 'notifications', type_='foreignkey')
    op.drop_column('notifications', 'actor_token')
    op.drop_column('notifications', 'kind')
