"""Make user id to be long

Revision ID: be484e4c9d87
Revises: f27b3aa40634
Create Date: 2024-11-23 08:24:16.461214

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'be484e4c9d87'
down_revision: str | None = 'f27b3aa40634'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('users', 'id',
               existing_type=mysql.INTEGER(display_width=11),
               type_=sa.BigInteger(),
               existing_nullable=False,
               autoincrement=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('users', 'id',
               existing_type=sa.BigInteger(),
               type_=mysql.INTEGER(display_width=11),
               existing_nullable=False,
               autoincrement=True)
    # ### end Alembic commands ###