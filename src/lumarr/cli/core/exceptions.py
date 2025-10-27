"""Custom CLI exceptions."""


class LumarrError(Exception):
    """Base exception for Lumarr CLI errors."""
    pass


class ConfigurationError(LumarrError):
    """Raised when configuration is invalid or missing."""
    pass


class ConnectionError(LumarrError):
    """Raised when unable to connect to a service."""
    pass


class SyncError(LumarrError):
    """Raised when sync operation fails."""
    pass
