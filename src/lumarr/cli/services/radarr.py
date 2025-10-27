"""Radarr API service wrapper."""

from ...api.radarr import RadarrApi


class RadarrService:
    """
    Radarr API service wrapper with context manager support.

    Provides factory methods and automatic resource management.
    """

    def __init__(self, api: RadarrApi):
        """
        Initialize Radarr service.

        Args:
            api: RadarrApi instance
        """
        self._api = api

    @classmethod
    def from_config(cls, config):
        """
        Create RadarrService from configuration.

        Args:
            config: Config object

        Returns:
            RadarrService instance
        """
        api = RadarrApi(
            url=config.get("radarr.url"),
            api_key=config.get("radarr.api_key"),
            quality_profile=config.get("radarr.quality_profile", 1),
            root_folder=config.get("radarr.root_folder"),
            monitored=config.get("radarr.monitored", True),
            search_on_add=config.get("radarr.search_on_add", True),
        )
        return cls(api)

    def __enter__(self):
        """Enter context manager - return API instance."""
        return self._api

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager - cleanup if needed."""
        return False

    def test_connection(self):
        """Test Radarr connection."""
        return self._api.test_connection()
