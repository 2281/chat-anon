"""add conversations

Revision ID: bc1ab3c10b49
Revises: 661dce435947
Create Date: 2026-11-04 21:59:56.433214

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bc1ab3c10b49'
down_revision: Union[str, Sequence[str], None] = '661dce435947'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('conversations',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('conversation_members',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('conversation_id', sa.BigInteger(), nullable=False),
    sa.Column('participant_token', sa.Uuid(), nullable=False),
    sa.Column('last_read_message_id', sa.BigInteger(), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['participant_token'], ['participants.token'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_conversation_members_conversation_id'), 'conversation_members', ['conversation_id'], unique=False)
    op.create_index(op.f('ix_conversation_members_participant_token'), 'conversation_members', ['participant_token'], unique=False)
    op.add_column('messages', sa.Column('conversation_id', sa.BigInteger(), nullable=True))
    op.create_index(op.f('ix_messages_conversation_id'), 'messages', ['conversation_id'], unique=False)
    op.create_foreign_key('fk_messages_conversation_id', 'messages', 'conversations', ['conversation_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_messages_conversation_id', 'messages', type_='foreignkey')
    op.drop_index(op.f('ix_messages_conversation_id'), table_name='messages')
    op.drop_column('messages', 'conversation_id')
    op.drop_index(op.f('ix_conversation_members_participant_token'), table_name='conversation_members')
    op.drop_index(op.f('ix_conversation_members_conversation_id'), table_name='conversation_members')
    op.drop_table('conversation_members')
    op.drop_table('conversations')
