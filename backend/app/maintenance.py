"""Explicit retention command: python -m app.maintenance --days 30 [--execute]."""

import argparse
from datetime import timedelta

from sqlalchemy import delete, func, select

from app.core.config import Settings
from app.core.security import utcnow
from app.database.connection import Database
from app.database.models import TelemetryReading


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.days < 1:
        parser.error("--days must be >=1")
    database = Database(Settings())
    cutoff = utcnow() - timedelta(days=args.days)
    with database.session() as db:
        count = db.scalar(
            select(func.count())
            .select_from(TelemetryReading)
            .where(TelemetryReading.received_at < cutoff)
        )
        print(f"Eligible telemetry rows: {count}; cutoff UTC: {cutoff.isoformat()}")
        if args.execute:
            deleted = 0
            while True:
                ids = list(
                    db.scalars(
                        select(TelemetryReading.id)
                        .where(TelemetryReading.received_at < cutoff)
                        .limit(10000)
                    )
                )
                if not ids:
                    break
                db.execute(delete(TelemetryReading).where(TelemetryReading.id.in_(ids)))
                db.commit()
                deleted += len(ids)
            print(f"Deleted telemetry rows: {deleted}")


if __name__ == "__main__":
    main()
