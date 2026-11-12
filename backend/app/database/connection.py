from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings


class Database:
    def __init__(self, settings: Settings):
        sqlite = str(settings.db_url).startswith("sqlite")
        connect_args = {"check_same_thread": False} if sqlite else {"connect_timeout": 5}
        self.engine = create_engine(settings.db_url, pool_pre_ping=True, connect_args=connect_args)
        self.session = sessionmaker(self.engine, expire_on_commit=False)

    def health(self) -> bool:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
