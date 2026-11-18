"""Add independent CAN history, latest frames and per-device DBC storage."""

from alembic import op

from app.database.models import CanDbc, CanFrame, CanLatest

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    for table in (CanFrame.__table__, CanLatest.__table__, CanDbc.__table__):
        table.create(op.get_bind())


def downgrade():
    for table in (CanDbc.__table__, CanLatest.__table__, CanFrame.__table__):
        table.drop(op.get_bind())
