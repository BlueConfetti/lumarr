"""Database service with context manager support."""

from pathlib import Path

from ...db import Database


class DatabaseService:
    """
    Database service wrapper with context manager support.

    Provides automatic resource management for database connections.
    """

    def __init__(self, db_path: str | Path):
        """
        Initialize database service.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._db = None

    def __enter__(self):
        """Enter context manager - initialize database."""
        self._db = Database(str(self.db_path))
        return self._db

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager - cleanup if needed."""
        # Database class doesn't require explicit cleanup
        # but this hook is here if needed in the future
        self._db = None
        return False  # Don't suppress exceptions
