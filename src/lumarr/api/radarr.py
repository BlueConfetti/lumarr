"""Radarr API client for movie management."""

import requests
from typing import Optional

from ..models import ProviderId


class RadarrApiError(Exception):
    """Radarr API error."""
    pass


class RadarrApi:
    """Client for Radarr API."""

    def __init__(
        self,
        url: str,
        api_key: str,
        quality_profile: int,
        root_folder: str,
        monitored: bool = True,
        search_on_add: bool = True,
    ):
        """Initialize Radarr API client.

        Args:
            url: Radarr base URL
            api_key: Radarr API key
            quality_profile: Quality profile ID
            root_folder: Root folder path
            monitored: Monitor movie
            search_on_add: Search for movie immediately after adding
        """
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.quality_profile = quality_profile
        self.root_folder = root_folder
        self.monitored = monitored
        self.search_on_add = search_on_add
        self.session = requests.Session()

    def _get_headers(self) -> dict:
        """Get headers for Radarr API requests.

        Returns:
            Dictionary of headers
        """
        return {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def test_connection(self) -> bool:
        """Test Radarr connection.

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
        """Get all quality profiles from Radarr.

        Returns:
            List of quality profile dictionaries with id and name

        Raises:
            RadarrApiError: If API request fails
        """
        try:
            response = self.session.get(
                f"{self.url}/api/v3/qualityProfile",
                headers=self._get_headers(),
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise RadarrApiError(f"Failed to fetch quality profiles: {e}")

    def get_root_folders(self) -> list[dict]:
        """Get all root folders from Radarr.

        Returns:
            List of root folder dictionaries with id, path, and freeSpace

        Raises:
            RadarrApiError: If API request fails
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
            raise RadarrApiError(f"Failed to fetch root folders: {e}")

    def get_tags(self) -> list[dict]:
        """Get all tags from Radarr.

        Returns:
            List of tag dictionaries with id and label

        Raises:
            RadarrApiError: If API request fails
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
            raise RadarrApiError(f"Failed to fetch tags: {e}")

    def get_movie_by_tmdb_id(self, tmdb_id: str) -> Optional[dict]:
        """Get movie by TMDB ID.

        Args:
            tmdb_id: TMDB ID

        Returns:
            Movie dict or None if not found
        """
        try:
            response = self.session.get(
                f"{self.url}/api/v3/movie",
                headers=self._get_headers(),
                timeout=10,
            )
            response.raise_for_status()

            all_movies = response.json()
            for movie in all_movies:
                if str(movie.get("tmdbId")) == str(tmdb_id):
                    return movie

            return None
        except requests.RequestException:
            return None

    def lookup_movie(self, tmdb_id: str) -> Optional[dict]:
        """Lookup movie information from Radarr.

        Args:
            tmdb_id: TMDB ID

        Returns:
            Movie lookup result or None
        """
        try:
            response = self.session.get(
                f"{self.url}/api/v3/movie/lookup/tmdb",
                params={"tmdbId": tmdb_id},
                headers=self._get_headers(),
                timeout=10,
            )
            response.raise_for_status()

            result = response.json()
            return result if result else None
        except requests.RequestException:
            return None

    def add_movie(
        self,
        provider_ids: ProviderId,
        title: str,
        year: Optional[int] = None,
    ) -> dict:
        """Add a movie to Radarr.

        Args:
            provider_ids: Provider IDs for the movie
            title: Movie title
            year: Release year

        Returns:
            Result dictionary with success status and message

        Raises:
            RadarrApiError: If movie cannot be added
        """
        if not provider_ids.tmdb_id:
            raise RadarrApiError("TMDB ID is required for Radarr")

        existing = self.get_movie_by_tmdb_id(provider_ids.tmdb_id)
        if existing:
            return {
                "success": True,
                "message": f"Movie already exists in Radarr: {existing.get('title')}",
                "movie": existing,
            }

        lookup_result = self.lookup_movie(provider_ids.tmdb_id)
        if not lookup_result:
            raise RadarrApiError(
                f"Could not find movie with TMDB ID {provider_ids.tmdb_id} in Radarr"
            )

        payload = {
            "title": lookup_result.get("title", title),
            "tmdbId": int(provider_ids.tmdb_id),
            "qualityProfileId": self.quality_profile,
            "rootFolderPath": self.root_folder,
            "monitored": self.monitored,
            "addOptions": {
                "searchForMovie": self.search_on_add,
            },
        }

        if year:
            payload["year"] = year

        if provider_ids.imdb_id:
            payload["imdbId"] = provider_ids.imdb_id

        try:
            response = self.session.post(
                f"{self.url}/api/v3/movie",
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
                raise RadarrApiError(
                    f"Failed to add movie: {'; '.join(error_messages)}"
                )

            response.raise_for_status()
            movie_data = response.json()

            return {
                "success": True,
                "message": f"Successfully added movie: {movie_data.get('title')}",
                "movie": movie_data,
            }

        except requests.RequestException as e:
            raise RadarrApiError(f"Failed to add movie to Radarr: {e}")
