"""Plex API client for watchlist operations."""

import logging
import re
import xml.etree.ElementTree as ET
import requests
from typing import TYPE_CHECKING, Optional

from ..models import MediaType, ProviderId, WatchlistItem

if TYPE_CHECKING:
    from ..db import Database

logger = logging.getLogger(__name__)


class PlexApiError(Exception):
    """Plex API error."""
    pass


class PlexApi:
    """Client for Plex watchlist API."""

    WATCHLIST_URI = "https://discover.provider.plex.tv"
    RSS_URI = "https://rss.plex.tv"
    APPLICATION_NAME = "lumarr"
    VERSION = "1.0"

    def __init__(
        self,
        auth_token: str,
        client_identifier: str,
        database: Optional["Database"] = None,
        cache_max_age_days: int = 7,
        rss_id: Optional[str] = None,
    ):
        """Initialize Plex API client.

        Args:
            auth_token: Plex authentication token
            client_identifier: Unique client identifier
            database: Optional database for metadata caching
            cache_max_age_days: Maximum age of cached metadata in days
            rss_id: Optional RSS feed ID for watchlist (alternative to API)
        """
        self.auth_token = auth_token
        self.client_identifier = client_identifier
        self.database = database
        self.cache_max_age_days = cache_max_age_days
        self.rss_id = rss_id
        self.session = requests.Session()

    def _get_headers(self) -> dict:
        """Get headers for Plex API requests.

        Returns:
            Dictionary of headers
        """
        return {
            "X-Plex-Token": self.auth_token,
            "X-Plex-Client-Identifier": self.client_identifier,
            "X-Plex-Product": self.APPLICATION_NAME,
            "X-Plex-Version": self.VERSION,
            "X-Plex-Device": "CLI",
            "X-Plex-Platform": "CLI",
            "Accept": "application/json",
        }

    def ping(self) -> bool:
        """Test if the Plex token is valid.

        Returns:
            True if token is valid, False otherwise
        """
        try:
            response = self.session.get(
                f"{self.WATCHLIST_URI}/library/sections/watchlist/all",
                headers=self._get_headers(),
                timeout=10,
            )
            return response.status_code not in [401, 403, 402]
        except requests.RequestException:
            return False

    def get_watchlist(self, force_refresh: bool = False) -> list[WatchlistItem]:
        """Fetch watchlist from Plex.

        Args:
            force_refresh: If True, bypass cache and fetch fresh metadata

        Returns:
            List of watchlist items

        Raises:
            PlexApiError: If API request fails
        """
        # Use RSS feed if rss_id is provided
        if self.rss_id:
            logger.debug("Using RSS feed for watchlist")
            return self._get_watchlist_from_rss()

        # Otherwise use API
        try:
            # Fetch watchlist overview with pagination
            all_metadata = []
            page_size = 50
            start = 0
            total_size = None

            while True:
                response = self.session.get(
                    f"{self.WATCHLIST_URI}/library/sections/watchlist/all",
                    headers=self._get_headers(),
                    params={
                        "X-Plex-Container-Start": start,
                        "X-Plex-Container-Size": page_size,
                    },
                    timeout=30,
                )

                if response.status_code in [401, 403, 402]:
                    raise PlexApiError(
                        f"Authentication failed (HTTP {response.status_code}). "
                        "Please check your Plex token."
                    )

                response.raise_for_status()
                data = response.json()

                media_container = data.get("MediaContainer", {})
                metadata_list = media_container.get("Metadata", [])

                # Get total size from first response
                if total_size is None:
                    total_size = media_container.get("totalSize", len(metadata_list))
                    logger.debug(f"Fetching {total_size} items from watchlist")

                all_metadata.extend(metadata_list)

                # Check if we've fetched everything
                if len(all_metadata) >= total_size or len(metadata_list) == 0:
                    break

                start += page_size
                logger.debug(f"Fetching page starting at {start}")

            metadata_list = all_metadata
            logger.debug(f"Retrieved {len(metadata_list)} items from watchlist")

            # Check which items need detailed metadata (don't have Guid array)
            needs_details = []
            for metadata in metadata_list:
                rating_key = metadata.get("ratingKey", "")
                if not metadata.get("Guid") and rating_key:
                    needs_details.append(rating_key)

            if not needs_details:
                # All items have Guid already, parse directly
                items = []
                for metadata in metadata_list:
                    item = self._parse_metadata(metadata)
                    if item:
                        items.append(item)
                return items

            # Use caching for detailed metadata if database available
            detailed_metadata_map = {}

            if self.database and not force_refresh:
                detailed_metadata_map = self._fetch_with_cache(needs_details)
            else:
                detailed_metadata_map = self._fetch_without_cache(needs_details)

            # Merge detailed metadata back into metadata_list
            items = []
            for metadata in metadata_list:
                rating_key = metadata.get("ratingKey", "")
                if rating_key in detailed_metadata_map:
                    metadata = detailed_metadata_map[rating_key]

                item = self._parse_metadata(metadata)
                if item:
                    items.append(item)

            return items

        except requests.RequestException as e:
            raise PlexApiError(f"Failed to fetch watchlist: {e}")

    def _fetch_with_cache(self, rating_keys: list[str]) -> dict[str, dict]:
        """Fetch metadata using cache when possible.

        Args:
            rating_keys: List of rating keys to fetch

        Returns:
            Dictionary mapping rating_key to metadata
        """
        # Check cache for all rating keys
        cached = self.database.get_multiple_metadata_cache(rating_keys)

        # Separate into fresh cache hits and stale/missing items
        fresh_cache = {}
        needs_fetch = []

        for rating_key in rating_keys:
            if rating_key in cached:
                if not self.database.is_cache_stale(rating_key, self.cache_max_age_days):
                    fresh_cache[rating_key] = cached[rating_key]["metadata"]
                else:
                    needs_fetch.append(rating_key)
            else:
                needs_fetch.append(rating_key)

        if needs_fetch:
            logger.debug(
                f"Cache: {len(fresh_cache)} hits, {len(needs_fetch)} misses - "
                f"fetching {len(needs_fetch)} items"
            )
            # Batch fetch missing/stale items
            fetched = self.get_batch_metadata(needs_fetch)

            # Store in cache
            if fetched:
                self.database.set_multiple_metadata_cache(fetched)

            # Merge with fresh cache
            fresh_cache.update(fetched)
        else:
            logger.debug(f"Cache: All {len(fresh_cache)} items from cache")

        return fresh_cache

    def _fetch_without_cache(self, rating_keys: list[str]) -> dict[str, dict]:
        """Fetch metadata without using cache.

        Args:
            rating_keys: List of rating keys to fetch

        Returns:
            Dictionary mapping rating_key to metadata
        """
        logger.debug(f"Fetching {len(rating_keys)} items without cache")
        return self.get_batch_metadata(rating_keys)

    def get_watchlist_metadata(self, rating_key: str) -> Optional[dict]:
        """Fetch detailed metadata for a watchlist item.

        Args:
            rating_key: Plex rating key

        Returns:
            Metadata dictionary or None if not found
        """
        try:
            response = self.session.get(
                f"{self.WATCHLIST_URI}/library/metadata/{rating_key}",
                headers=self._get_headers(),
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            metadata_list = data.get("MediaContainer", {}).get("Metadata", [])
            return metadata_list[0] if metadata_list else None
        except requests.RequestException:
            return None

    def get_batch_metadata(self, rating_keys: list[str]) -> dict[str, dict]:
        """Fetch detailed metadata for multiple watchlist items in a single request.

        Args:
            rating_keys: List of Plex rating keys

        Returns:
            Dictionary mapping rating_key to metadata dict
        """
        if not rating_keys:
            return {}

        # Plex API accepts comma-separated rating keys
        ids_param = ",".join(rating_keys)

        try:
            response = self.session.get(
                f"{self.WATCHLIST_URI}/library/metadata/{ids_param}",
                headers=self._get_headers(),
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            metadata_list = data.get("MediaContainer", {}).get("Metadata", [])

            # Build dict mapping rating_key to metadata
            result = {}
            for metadata in metadata_list:
                rating_key = metadata.get("ratingKey", "")
                if rating_key:
                    result[rating_key] = metadata

            return result
        except requests.RequestException as e:
            logger.warning(f"Batch metadata fetch failed: {e}")
            return {}

    def _parse_metadata(self, metadata: dict) -> Optional[WatchlistItem]:
        """Parse metadata into WatchlistItem.

        Args:
            metadata: Metadata dictionary from Plex API

        Returns:
            WatchlistItem or None if type is not supported
        """
        media_type_str = metadata.get("type", "").lower()

        if media_type_str == "movie":
            media_type = MediaType.MOVIE
        elif media_type_str == "show":
            media_type = MediaType.TV_SHOW
        else:
            return None

        guids = []
        for guid_obj in metadata.get("Guid", []):
            guid = guid_obj.get("id", "")
            if guid:
                guids.append(guid)

        provider_ids = self._extract_provider_ids(guids)

        genres = []
        for genre_obj in metadata.get("Genre", []):
            tag = genre_obj.get("tag", "")
            if tag:
                genres.append(tag)

        return WatchlistItem(
            rating_key=metadata.get("ratingKey", ""),
            title=metadata.get("title", ""),
            media_type=media_type,
            year=metadata.get("year"),
            guids=guids,
            provider_ids=provider_ids,
            content_rating=metadata.get("contentRating"),
            summary=metadata.get("summary"),
            genres=genres,
            studio=metadata.get("studio"),
            added_at=metadata.get("addedAt"),
        )

    def _extract_provider_ids(self, guids: list[str]) -> ProviderId:
        """Extract provider IDs from Plex GUIDs.

        Args:
            guids: List of Plex GUID strings (API or RSS format)

        Returns:
            ProviderId object with extracted IDs
        """
        provider_ids = ProviderId()

        for guid in guids:
            if not guid:
                continue

            # TMDB: com.plexapp.agents.themoviedb://123456 or tmdb://123456 (RSS)
            if "tmdb://" in guid.lower():
                match = re.search(r"tmdb://(\d+)", guid, re.IGNORECASE)
                if match:
                    provider_ids.tmdb_id = match.group(1)

            # TVDB: com.plexapp.agents.thetvdb://269586 or tvdb://269586 (RSS)
            elif "tvdb://" in guid.lower():
                match = re.search(r"tvdb://(\d+)", guid, re.IGNORECASE)
                if match:
                    provider_ids.tvdb_id = match.group(1)

            # IMDB: com.plexapp.agents.imdb://tt2543164 or imdb://tt2543164 (RSS)
            elif "imdb://" in guid.lower():
                match = re.search(r"imdb://(tt\d+)", guid, re.IGNORECASE)
                if match:
                    provider_ids.imdb_id = match.group(1)

            # Plex native GUID: plex://movie/5e1632df2d4d84003e48e54e
            # These don't contain external IDs directly

        return provider_ids

    def _get_watchlist_from_rss(self) -> list[WatchlistItem]:
        """Fetch watchlist from RSS feed.

        Returns:
            List of watchlist items

        Raises:
            PlexApiError: If RSS request fails
        """
        try:
            rss_url = f"{self.RSS_URI}/{self.rss_id}"
            logger.debug(f"Fetching RSS feed from {rss_url}")

            response = self.session.get(rss_url, timeout=30)
            response.raise_for_status()

            # Parse XML
            root = ET.fromstring(response.content)

            # Define namespaces
            namespaces = {
                "media": "http://search.yahoo.com/mrss/",
                "atom": "http://www.w3.org/2005/Atom",
            }

            items = []
            for item_elem in root.findall(".//item"):
                watchlist_item = self._parse_rss_item(item_elem, namespaces)
                if watchlist_item:
                    items.append(watchlist_item)

            logger.debug(f"Parsed {len(items)} items from RSS feed")
            return items

        except requests.RequestException as e:
            raise PlexApiError(f"Failed to fetch RSS feed: {e}")
        except ET.ParseError as e:
            raise PlexApiError(f"Failed to parse RSS feed: {e}")

    def _parse_rss_item(self, item_elem: ET.Element, namespaces: dict) -> Optional[WatchlistItem]:
        """Parse a single RSS item into WatchlistItem.

        Args:
            item_elem: XML element for the item
            namespaces: XML namespaces dictionary

        Returns:
            WatchlistItem or None if parsing fails
        """
        try:
            # Get title and extract year
            title_text = item_elem.findtext("title", "")
            title, year = self._parse_title_and_year(title_text)

            # Get category (movie or show)
            category = item_elem.findtext("category", "").lower()
            if category == "movie":
                media_type = MediaType.MOVIE
            elif category == "show":
                media_type = MediaType.TV_SHOW
            else:
                logger.warning(f"Unknown category: {category}")
                return None

            # Get provider ID from guid
            guid = item_elem.findtext("guid", "")
            provider_ids = self._extract_provider_ids([guid])

            # Get genres from media:keywords
            keywords_elem = item_elem.find("media:keywords", namespaces)
            genres = []
            if keywords_elem is not None and keywords_elem.text:
                genres = [g.strip() for g in keywords_elem.text.split(",")]

            # Get content rating from media:rating
            content_rating = None
            for rating_elem in item_elem.findall("media:rating", namespaces):
                scheme = rating_elem.get("scheme", "")
                if "mpaa" in scheme or "v-chip" in scheme:
                    content_rating = rating_elem.text
                    break

            # Get summary from description
            summary = item_elem.findtext("description", "")

            # Use guid as rating_key since RSS doesn't have ratingKey
            rating_key = guid.replace("://", "_")

            return WatchlistItem(
                rating_key=rating_key,
                title=title,
                media_type=media_type,
                year=year,
                guids=[guid] if guid else [],
                provider_ids=provider_ids,
                content_rating=content_rating,
                summary=summary,
                genres=genres,
                studio=None,  # RSS doesn't include studio
                added_at=None,  # Could parse pubDate if needed
            )

        except Exception as e:
            logger.warning(f"Failed to parse RSS item: {e}")
            return None

    def _parse_title_and_year(self, title_text: str) -> tuple[str, Optional[int]]:
        """Parse title and year from RSS title format 'Title (Year)'.

        Args:
            title_text: Title string in format "Title (Year)"

        Returns:
            Tuple of (title, year)
        """
        match = re.search(r"^(.+?)\s*\((\d{4})\)\s*$", title_text)
        if match:
            title = match.group(1).strip()
            year = int(match.group(2))
            return title, year
        return title_text, None
