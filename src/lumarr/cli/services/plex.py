"""Plex API service wrapper."""

from ...api.plex import PlexApi


class PlexService:
    """
    Plex API service wrapper with context manager support.

    Provides factory methods and automatic resource management.
    """

    def __init__(self, api: PlexApi):
        """
        Initialize Plex service.

        Args:
            api: PlexApi instance
        """
        self._api = api

    @classmethod
    def from_config(cls, config, database):
        """
        Create PlexService from configuration.

        Args:
            config: Config object
            database: Database instance for caching

        Returns:
            PlexService instance
        """
        api = PlexApi(
            auth_token=config.get("plex.token"),
            client_identifier=config.get("plex.client_identifier", "lumarr"),
            database=database,
            cache_max_age_days=config.get("sync.cache_max_age_days", 7),
            rss_id=config.get("plex.rss_id"),
        )
        return cls(api)

    def __enter__(self):
        """Enter context manager - return API instance."""
        return self._api

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager - cleanup if needed."""
        # PlexApi doesn't require explicit cleanup
        return False

    def ping(self):
        """Test Plex connection."""
        return self._api.ping()
