"""Match the user's confirmed six onboard ADC1 channels; no external hardware.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import INTEGER

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("telemetry_readings") as table:
        for i in range(7, 11):
            table.drop_column(f"analog_{i}")


def downgrade():
    # Values for removed channels cannot be recovered; defaults permit a structural rollback.
    with op.batch_alter_table("telemetry_readings") as table:
        for i in range(7, 11):
            table.add_column(
                sa.Column(
                    f"analog_{i}",
                    sa.Integer().with_variant(INTEGER(unsigned=True), "mysql"),
                    nullable=False,
                    server_default="0",
                )
            )
