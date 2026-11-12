from alembic import context

from app.core.config import Settings
from app.database.connection import Database
from app.database.models import Base

target_metadata = Base.metadata


def offline():
    context.configure(url=Settings().db_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def online():
    engine = Database(Settings()).engine
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    offline()
else:
    online()
