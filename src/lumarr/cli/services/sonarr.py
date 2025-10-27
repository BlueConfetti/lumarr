"""Sonarr API service wrapper."""

from ...api.sonarr import SonarrApi


class SonarrService:
    """
    Sonarr API service wrapper with context manager support.

    Provides factory methods and automatic resource management.
    """

    def __init__(self, api: SonarrApi):
        """
        Initialize Sonarr service.

        Args:
            api: SonarrApi instance
        """
        self._api = api

    @classmethod
    def from_config(cls, config):
        """
        Create SonarrService from configuration.

        Args:
            config: Config object

        Returns:
            SonarrService instance
        """
        api = SonarrApi(
            url=config.get("sonarr.url"),
            api_key=config.get("sonarr.api_key"),
            quality_profile=config.get("sonarr.quality_profile", 1),
            root_folder=config.get("sonarr.root_folder"),
            series_type=config.get("sonarr.series_type", "standard"),
            season_folder=config.get("sonarr.season_folder", True),
            monitor_all=config.get("sonarr.monitor_all", False),
        )
        return cls(api)

    def __enter__(self):
        """Enter context manager - return API instance."""
        return self._api

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager - cleanup if needed."""
        return False

    def test_connection(self):
        """Test Sonarr connection."""
        return self._api.test_connection()
