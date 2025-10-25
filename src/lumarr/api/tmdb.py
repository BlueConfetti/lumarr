"""TMDB API client for ID lookups."""

import requests
from typing import Optional

from ..models import ProviderId


class TmdbApiError(Exception):
    """TMDB API error."""
    pass


class TmdbApi:
    """Client for The Movie Database API."""

    BASE_URL = "https://api.themoviedb.org/3"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize TMDB API client.

        Args:
            api_key: TMDB API key (optional)
        """
        self.api_key = api_key
        self.session = requests.Session()

    def is_configured(self) -> bool:
        """Check if API key is configured.

        Returns:
            True if API key is set
        """
        return bool(self.api_key)

    def find_by_external_id(
        self, external_id: str, external_source: str
    ) -> Optional[dict]:
        """Find media by external ID.

        Args:
            external_id: External ID (IMDB or TVDB)
            external_source: Source type ('imdb_id' or 'tvdb_id')

        Returns:
            Result dictionary or None if not found
        """
        if not self.is_configured():
            return None

        try:
            response = self.session.get(
                f"{self.BASE_URL}/find/{external_id}",
                params={
                    "api_key": self.api_key,
                    "external_source": external_source,
                },
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            return None

    def enhance_provider_ids(
        self, provider_ids: ProviderId, media_type: str
    ) -> ProviderId:
        """Enhance provider IDs using TMDB lookups.

        Args:
            provider_ids: Existing provider IDs
            media_type: Type of media ('movie' or 'show')

        Returns:
            Enhanced ProviderId object
        """
        if not self.is_configured():
            return provider_ids

        if provider_ids.tmdb_id:
            return provider_ids

        result = None

        if provider_ids.tvdb_id:
            result = self.find_by_external_id(provider_ids.tvdb_id, "tvdb_id")

        if not result and provider_ids.imdb_id:
            result = self.find_by_external_id(provider_ids.imdb_id, "imdb_id")

        if not result:
            return provider_ids

        if media_type == "movie" and result.get("movie_results"):
            movie = result["movie_results"][0]
            provider_ids.tmdb_id = str(movie.get("id", ""))

        elif media_type == "show" and result.get("tv_results"):
            show = result["tv_results"][0]
            provider_ids.tmdb_id = str(show.get("id", ""))
            if not provider_ids.tvdb_id:
                tvdb_id = show.get("external_ids", {}).get("tvdb_id")
                if tvdb_id:
                    provider_ids.tvdb_id = str(tvdb_id)

        return provider_ids

    def search_movie(self, title: str, year: Optional[int] = None) -> Optional[str]:
        """Search TMDB for a movie by title (and optional year) and return its ID."""
        if not self.is_configured() or not title:
            return None

        params = {
            "api_key": self.api_key,
            "query": title,
        }
        if year:
            params["primary_release_year"] = year

        try:
            response = self.session.get(
                f"{self.BASE_URL}/search/movie",
                params=params,
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException:
            return None

        results = data.get("results") or []
        if not results:
            return None

        best_match = results[0]
        tmdb_id = best_match.get("id")
        return str(tmdb_id) if tmdb_id else None
