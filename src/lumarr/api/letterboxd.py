"""Letterboxd RSS and watchlist client."""

import logging
import re
import time
import xml.etree.ElementTree as ET
from html import unescape
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple

import requests

from ..models import MediaType, ProviderId, WatchlistItem

logger = logging.getLogger(__name__)


class LetterboxdApiError(Exception):
    """Letterboxd API error."""


class _WatchlistPosterParser(HTMLParser):
    """Lightweight parser to extract LazyPoster blocks from watchlist pages."""

    def __init__(self):
        super().__init__()
        self.items: List[Dict[str, str]] = []

    def handle_starttag(self, tag, attrs):
        if tag != "div":
            return
        attr_dict = dict(attrs)
        if attr_dict.get("data-component-class") == "LazyPoster":
            self.items.append(attr_dict)


class LetterboxdApi:
    """Client for Letterboxd RSS feeds and watchlists."""

    RSS_URL_TEMPLATE = "https://letterboxd.com/{username}/rss/"
    WATCHLIST_URL_TEMPLATE = "https://letterboxd.com/{username}/watchlist/"
    WATCHLIST_PAGED_URL_TEMPLATE = "https://letterboxd.com/{username}/watchlist/page/{page}/"
    WATCHLIST_REQUEST_DELAY = 0.5  # seconds
    MAX_REQUEST_RETRIES = 3

    def __init__(
        self,
        usernames: Optional[List[str]] = None,
        watchlist_usernames: Optional[List[str]] = None,
    ):
        self.usernames = usernames or []
        self.watchlist_usernames = watchlist_usernames or []

    # ------------------------------------------------------------------ RSS --
    def get_watched_movies(self, usernames: Optional[List[str]] = None) -> List[WatchlistItem]:
        """Fetch watched movies from all configured users' RSS feeds."""
        target_usernames = usernames if usernames is not None else self.usernames

        all_items: List[WatchlistItem] = []
        for username in target_usernames:
            logger.debug("Fetching Letterboxd RSS feed for user: %s", username)
            items = self._fetch_user_feed(username)
            all_items.extend(items)
            logger.debug("Found %d watched items for %s", len(items), username)

        logger.debug("Total watched items across all users: %d", len(all_items))
        return all_items

    def _fetch_user_feed(self, username: str) -> List[WatchlistItem]:
        url = self.RSS_URL_TEMPLATE.format(username=username)

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise LetterboxdApiError(f"Failed to fetch RSS feed for {username}: {exc}") from exc

        try:
            return self._parse_rss_feed(response.text, username)
        except ET.ParseError as exc:
            raise LetterboxdApiError(f"Failed to parse RSS feed for {username}: {exc}") from exc

    def _parse_rss_feed(self, xml_content: str, username: str) -> List[WatchlistItem]:
        root = ET.fromstring(xml_content)

        namespaces = {
            "letterboxd": "https://letterboxd.com",
            "tmdb": "https://themoviedb.org",
            "dc": "http://purl.org/dc/elements/1.1/",
        }

        items: List[WatchlistItem] = []
        channel = root.find("channel")
        if channel is None:
            return items

        for item_elem in channel.findall("item"):
            try:
                item = self._parse_rss_item(item_elem, namespaces, username)
                if item:
                    items.append(item)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed to parse RSS item for %s: %s", username, exc)
                continue

        return items

    def _parse_rss_item(
        self,
        item_elem: ET.Element,
        namespaces: Dict[str, str],
        username: str,
    ) -> Optional[WatchlistItem]:
        film_title_elem = item_elem.find("letterboxd:filmTitle", namespaces)
        film_year_elem = item_elem.find("letterboxd:filmYear", namespaces)

        if film_title_elem is None or film_title_elem.text is None:
            return None

        title = film_title_elem.text
        year = int(film_year_elem.text) if film_year_elem is not None and film_year_elem.text else None

        tmdb_id_elem = item_elem.find("tmdb:movieId", namespaces)
        tmdb_id = tmdb_id_elem.text if tmdb_id_elem is not None and tmdb_id_elem.text else None

        rating_elem = item_elem.find("letterboxd:memberRating", namespaces)
        rating = float(rating_elem.text) if rating_elem is not None and rating_elem.text else None

        watched_date_elem = item_elem.find("letterboxd:watchedDate", namespaces)
        watched_date = watched_date_elem.text if watched_date_elem is not None else None

        rewatch_elem = item_elem.find("letterboxd:rewatch", namespaces)
        is_rewatch = rewatch_elem is not None and rewatch_elem.text == "Yes"

        guid_elem = item_elem.find("guid")
        guid = guid_elem.text if guid_elem is not None and guid_elem.text else None

        rating_key = f"letterboxd-{username}-{guid}" if guid else f"letterboxd-{username}-{title}-{year}"

        provider_ids = ProviderId()
        if tmdb_id:
            provider_ids.tmdb_id = tmdb_id

        summary = None
        if watched_date:
            summary = f"Watched on {watched_date}"
            if is_rewatch:
                summary += " (Rewatch)"

        return WatchlistItem(
            rating_key=rating_key,
            title=title,
            year=year,
            media_type=MediaType.MOVIE,
            provider_ids=provider_ids,
            summary=summary,
            rating=rating,
            genres=[],
            content_rating=None,
            studio=None,
        )

    # ------------------------------------------------------------ Watchlist --
    def get_watchlist_movies(self, watchlist_usernames: Optional[List[str]] = None) -> List[WatchlistItem]:
        """Fetch movies from the specified Letterboxd watchlists."""
        target_usernames = watchlist_usernames if watchlist_usernames is not None else self.watchlist_usernames
        if not target_usernames:
            return []

        all_items: List[WatchlistItem] = []
        for username in target_usernames:
            logger.debug("Fetching Letterboxd watchlist for user: %s", username)
            items = self._fetch_watchlist_for_user(username)
            all_items.extend(items)
            logger.debug("Found %d watchlist items for %s", len(items), username)

        logger.debug("Total watchlist items across all users: %d", len(all_items))
        return all_items

    def _fetch_watchlist_for_user(self, username: str) -> List[WatchlistItem]:
        collected: List[WatchlistItem] = []
        seen_slugs: set[str] = set()
        total_expected: Optional[int] = None
        page = 1

        while True:
            if page == 1:
                url = self.WATCHLIST_URL_TEMPLATE.format(username=username)
            else:
                url = self.WATCHLIST_PAGED_URL_TEMPLATE.format(username=username, page=page)

            try:
                response = self._request_with_retry(url, self.WATCHLIST_REQUEST_DELAY)
                if response.status_code == 404:
                    if page == 1:
                        raise LetterboxdApiError(f"Watchlist not found for {username}")
                    break
            except requests.RequestException as exc:
                raise LetterboxdApiError(
                    f"Failed to fetch watchlist page {page} for {username}: {exc}"
                ) from exc

            html = response.text

            if total_expected is None:
                total_expected = self._extract_total_watchlist_count(html)

            parser = _WatchlistPosterParser()
            parser.feed(html)
            page_entries = parser.items

            if not page_entries:
                break

            for entry in page_entries:
                slug = entry.get("data-item-slug")
                if not slug:
                    slug = self._slug_from_link(entry.get("data-item-link"))
                if not slug or slug in seen_slugs:
                    continue

                try:
                    item = self._build_watchlist_item(entry, username, slug)
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning("Failed to parse watchlist entry '%s' for %s: %s", slug, username, exc)
                    continue

                collected.append(item)
                seen_slugs.add(slug)

            if total_expected is not None and len(collected) >= total_expected:
                break

            if not self._has_next_watchlist_page(html):
                break

            page += 1

        return collected

    def _build_watchlist_item(
        self,
        entry: Dict[str, str],
        username: str,
        slug: str,
    ) -> WatchlistItem:
        raw_name = entry.get("data-item-name") or entry.get("data-item-full-display-name") or slug.replace("-", " ")
        title, year = self._parse_title_year(raw_name)

        film_id = entry.get("data-film-id")
        rating_key = f"letterboxd-watchlist-{username}-{film_id or slug}"

        # Don't set TMDB ID here - it will be fetched lazily during sync
        provider_ids = ProviderId()

        return WatchlistItem(
            rating_key=rating_key,
            title=title,
            year=year,
            media_type=MediaType.MOVIE,
            provider_ids=provider_ids,
            summary=None,
            rating=None,
            genres=[],
            content_rating=None,
            studio=None,
            letterboxd_id=film_id,
            letterboxd_slug=slug,
        )

    @staticmethod
    def _slug_from_link(link: Optional[str]) -> Optional[str]:
        if not link:
            return None
        match = re.match(r"/film/([^/]+)/", link)
        return match.group(1) if match else None

    @staticmethod
    def _parse_title_year(raw_name: str) -> Tuple[str, Optional[int]]:
        text = unescape(raw_name or "").strip()
        match = re.match(r"^(.*?)(?:\s+\((\d{4})\))?$", text)
        if match:
            title = match.group(1).strip()
            year_text = match.group(2)
            year = int(year_text) if year_text else None
            return title, year
        return text, None

    @staticmethod
    def _extract_total_watchlist_count(html: str) -> Optional[int]:
        match = re.search(r'data-num-entries="(\d+)"', html)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None

    @staticmethod
    def _has_next_watchlist_page(html: str) -> bool:
        """Check if there is a next page by looking for the 'next' link in pagination."""
        return 'class="next"' in html and 'paginate-nextprev' in html

    def _request_with_retry(self, url: str, base_delay: float) -> requests.Response:
        delay = 0.0
        last_exception: Optional[requests.RequestException] = None

        for attempt in range(self.MAX_REQUEST_RETRIES):
            if delay > 0:
                time.sleep(delay)

            try:
                response = requests.get(url, timeout=30)
            except requests.RequestException as exc:
                last_exception = exc
                delay = base_delay * (attempt + 1)
                continue

            if response.status_code != 429:
                response.raise_for_status()
                return response

            retry_after = response.headers.get("Retry-After")
            try:
                delay = max(float(retry_after), base_delay)
            except (TypeError, ValueError):
                delay = base_delay * (attempt + 1)

        if last_exception:
            raise last_exception

        response.raise_for_status()
        return response

    def fetch_tmdb_id_from_page(self, slug: str) -> Optional[str]:
        """Fetch TMDB ID from a Letterboxd movie page.

        Args:
            slug: Film slug (e.g., 'the-godfather')

        Returns:
            TMDB ID string or None if not found
        """
        url = f"https://letterboxd.com/film/{slug}/"

        try:
            response = self._request_with_retry(url, self.WATCHLIST_REQUEST_DELAY)
            html = response.text

            # Look for data-tmdb-id in the body tag
            match = re.search(r'<body[^>]*\sdata-tmdb-id="(\d+)"', html)
            if match:
                tmdb_id = match.group(1)
                logger.debug(f"Extracted TMDB ID {tmdb_id} from {slug}")
                return tmdb_id

            logger.warning(f"Could not find TMDB ID on page for {slug}")
            return None

        except requests.RequestException as exc:
            logger.warning(f"Failed to fetch movie page for {slug}: {exc}")
            return None
