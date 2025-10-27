"""Core CLI infrastructure."""

from .context import LumarrContext
from .decorators import (
    with_config,
    with_database,
    with_plex,
    with_sonarr,
    with_radarr,
    with_tmdb,
    with_letterboxd,
)
from .exceptions import (
    LumarrError,
    ConfigurationError,
    ConnectionError,
    SyncError,
)
from .hooks import get_hook_manager, register_hook, trigger_hook
from .plugin_loader import LumarrGroup

__all__ = [
    # Context
    "LumarrContext",
    # Decorators
    "with_config",
    "with_database",
    "with_plex",
    "with_sonarr",
    "with_radarr",
    "with_tmdb",
    "with_letterboxd",
    # Exceptions
    "LumarrError",
    "ConfigurationError",
    "ConnectionError",
    "SyncError",
    # Hooks
    "get_hook_manager",
    "register_hook",
    "trigger_hook",
    # Plugin loader
    "LumarrGroup",
]
