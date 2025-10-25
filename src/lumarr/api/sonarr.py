"""Sonarr API client for TV show management."""

import requests
from typing import Optional

from ..models import ProviderId


class SonarrApiError(Exception):
    """Sonarr API error."""
    pass


class SonarrApi:
    """Client for Sonarr API."""

    def __init__(
        self,
        url: str,
        api_key: str,
        quality_profile: int,
        root_folder: str,
        series_type: str = "standard",
        season_folder: bool = True,
        monitor_all: bool = False,
    ):
        """Initialize Sonarr API client.

        Args:
            url: Sonarr base URL
            api_key: Sonarr API key
            quality_profile: Quality profile ID
            root_folder: Root folder path
            series_type: Series type (standard, daily, anime)
            season_folder: Use season folders
            monitor_all: Monitor all seasons or just latest
        """
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.quality_profile = quality_profile
        self.root_folder = root_folder
        self.series_type = series_type
        self.season_folder = season_folder
        self.monitor_all = monitor_all
        self.session = requests.Session()

    def _get_headers(self) -> dict:
        """Get headers for Sonarr API requests.

        Returns:
            Dictionary of headers
        """
        return {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def test_connection(self) -> bool:
        """Test Sonarr connection.

        Returns:
            True if connection successful
        """
        try:
            response = self.session.get(
                f"{self.url}/api/v3/system/status",
                headers=self._get_headers(),
                timeout=10,
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    def get_quality_profiles(self) -> list[dict]:
        """Get all quality profiles from Sonarr.

        Returns:
            List of quality profile dictionaries with id and name

        Raises:
            SonarrApiError: If API request fails
        """
        try:
            response = self.session.get(
                f"{self.url}/api/v3/qualityprofile",
                headers=self._get_headers(),
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise SonarrApiError(f"Failed to fetch quality profiles: {e}")

    def get_root_folders(self) -> list[dict]:
        """Get all root folders from Sonarr.

        Returns:
            List of root folder dictionaries with id, path, and freeSpace

        Raises:
            SonarrApiError: If API request fails
        """
        try:
            response = self.session.get(
                f"{self.url}/api/v3/rootfolder",
                headers=self._get_headers(),
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise SonarrApiError(f"Failed to fetch root folders: {e}")

    def get_tags(self) -> list[dict]:
        """Get all tags from Sonarr.

        Returns:
            List of tag dictionaries with id and label

        Raises:
            SonarrApiError: If API request fails
        """
        try:
            response = self.session.get(
                f"{self.url}/api/v3/tag",
                headers=self._get_headers(),
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise SonarrApiError(f"Failed to fetch tags: {e}")

    def get_series_by_tvdb_id(self, tvdb_id: str) -> Optional[dict]:
        """Get series by TVDB ID.

        Args:
            tvdb_id: TVDB ID

        Returns:
            Series dict or None if not found
        """
        try:
            response = self.session.get(
                f"{self.url}/api/v3/series",
                headers=self._get_headers(),
                timeout=10,
            )
            response.raise_for_status()

            all_series = response.json()
            for series in all_series:
                if str(series.get("tvdbId")) == str(tvdb_id):
                    return series

            return None
        except requests.RequestException:
            return None

    def lookup_series(self, tvdb_id: str) -> Optional[dict]:
        """Lookup series information from Sonarr.

        Args:
            tvdb_id: TVDB ID

        Returns:
            Series lookup result or None
        """
        try:
            response = self.session.get(
                f"{self.url}/api/v3/series/lookup",
                params={"term": f"tvdb:{tvdb_id}"},
                headers=self._get_headers(),
                timeout=10,
            )
            response.raise_for_status()

            results = response.json()
            return results[0] if results else None
        except requests.RequestException:
            return None

    def add_series(
        self,
        provider_ids: ProviderId,
        title: str,
    ) -> dict:
        """Add a TV series to Sonarr.

        Args:
            provider_ids: Provider IDs for the series
            title: Series title

        Returns:
            Result dictionary with success status and message

        Raises:
            SonarrApiError: If series cannot be added
        """
        if not provider_ids.tvdb_id:
            raise SonarrApiError("TVDB ID is required for Sonarr")

        existing = self.get_series_by_tvdb_id(provider_ids.tvdb_id)
        if existing:
            return {
                "success": True,
                "message": f"Series already exists in Sonarr: {existing.get('title')}",
                "series": existing,
            }

        lookup_result = self.lookup_series(provider_ids.tvdb_id)
        if not lookup_result:
            raise SonarrApiError(
                f"Could not find series with TVDB ID {provider_ids.tvdb_id} in Sonarr"
            )

        if self.monitor_all:
            monitored = True
            monitor_type = "all"
        else:
            monitored = True
            monitor_type = "future"

        payload = {
            "title": lookup_result.get("title", title),
            "tvdbId": int(provider_ids.tvdb_id),
            "qualityProfileId": self.quality_profile,
            "rootFolderPath": self.root_folder,
            "seriesType": self.series_type,
            "seasonFolder": self.season_folder,
            "monitored": monitored,
            "addOptions": {
                "monitor": monitor_type,
                "searchForMissingEpisodes": True,
            },
        }

        if provider_ids.imdb_id:
            payload["imdbId"] = provider_ids.imdb_id

        if provider_ids.tmdb_id:
            payload["tmdbId"] = int(provider_ids.tmdb_id)

        try:
            response = self.session.post(
                f"{self.url}/api/v3/series",
                headers=self._get_headers(),
                json=payload,
                timeout=30,
            )

            if response.status_code == 400:
                error_data = response.json()
                error_messages = []
                for error in error_data:
                    if "errorMessage" in error:
                        error_messages.append(error["errorMessage"])
                raise SonarrApiError(
                    f"Failed to add series: {'; '.join(error_messages)}"
                )

            response.raise_for_status()
            series_data = response.json()

            return {
                "success": True,
                "message": f"Successfully added series: {series_data.get('title')}",
                "series": series_data,
            }

        except requests.RequestException as e:
            raise SonarrApiError(f"Failed to add series to Sonarr: {e}")
