import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from .config import DATABASE_PATH


SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(database_path: Path = DATABASE_PATH) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def session(database_path: Path = DATABASE_PATH) -> Generator[sqlite3.Connection, None, None]:
    connection = connect(database_path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(database_path: Path = DATABASE_PATH) -> None:
    with session(database_path) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
