"""Independent BMS job and exchange audit history."""

from alembic import op

from app.database.models import BmsExchange, BmsJob

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    BmsJob.__table__.create(op.get_bind())
    BmsExchange.__table__.create(op.get_bind())


def downgrade():
    BmsExchange.__table__.drop(op.get_bind())
    BmsJob.__table__.drop(op.get_bind())
