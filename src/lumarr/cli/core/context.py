"""Application context for CLI."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ...config import Config


@dataclass
class LumarrContext:
    """Shared application context passed through Click commands."""

    config: Config
    config_path: Path
    db_path: Path
    database: Optional[any] = None  # Lazily initialized by decorators

    @classmethod
    def create(cls, config_path: str, db_path: Optional[str] = None):
        """
        Factory method to create context from paths.

        Args:
            config_path: Path to config file
            db_path: Path to database file (optional, resolved later)

        Returns:
            LumarrContext instance

        Raises:
            ConfigurationError: If config is invalid
        """
        from .exceptions import ConfigurationError

        try:
            config = Config(config_path)
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {e}")

        # Resolve database path: provided > config > default
        resolved_db_path = db_path or config.get("sync.database") or "./lumarr.db"

        return cls(
            config=config,
            config_path=Path(config_path),
            db_path=Path(resolved_db_path)
        )
