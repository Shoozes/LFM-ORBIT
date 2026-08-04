"""Small SQLite lifecycle helpers shared by runtime stores."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def managed_connection(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Commit successful work, roll back failures, and always close the handle."""
    try:
        yield connection
    except BaseException:
        connection.rollback()
        raise
    else:
        connection.commit()
    finally:
        connection.close()
