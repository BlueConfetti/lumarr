"""Sync orchestration for Plex watchlist to Sonarr/Radarr."""

import logging
from typing import Optional

from ...api.plex import PlexApi, PlexApiError
from ...api.radarr import RadarrApi, RadarrApiError
from ...api.sonarr import SonarrApi, SonarrApiError
from ...api.tmdb import TmdbApi
from ...db import Database
from ...models import MediaType, RequestStatus, SyncResult, SyncSummary, WatchlistItem

logger = logging.getLogger(__name__)


class SyncManager:
    """Manages synchronization between Plex watchlist and Sonarr/Radarr."""

    def __init__(
        self,
        plex: PlexApi,
        database: Database,
        sonarr: Optional[SonarrApi] = None,
        radarr: Optional[RadarrApi] = None,
        tmdb: Optional[TmdbApi] = None,
        dry_run: bool = False,
        force_refresh: bool = False,
    ):
        """Initialize sync manager.

        Args:
            plex: Plex API client
            database: Database for tracking synced items
            sonarr: Sonarr API client (optional)
            radarr: Radarr API client (optional)
            tmdb: TMDB API client (optional)
            dry_run: If True, don't actually add items
            force_refresh: If True, bypass metadata cache
        """
        self.plex = plex
        self.database = database
        self.sonarr = sonarr
        self.radarr = radarr
        self.tmdb = tmdb
        self.dry_run = dry_run
        self.force_refresh = force_refresh

    def sync(self) -> SyncSummary:
        """Sync Plex watchlist to Sonarr and Radarr.

        Returns:
            SyncSummary with results
        """
        summary = SyncSummary()

        logger.debug("Starting Plex watchlist sync")

        try:
            watchlist = self.plex.get_watchlist(force_refresh=self.force_refresh)
            summary.total = len(watchlist)
            logger.debug(f"Found {summary.total} items in Plex watchlist")

            for item in watchlist:
                result = self._sync_item(item)
                summary.results.append(result)

                if result.status == RequestStatus.SUCCESS:
                    if item.media_type == MediaType.MOVIE:
                        summary.movies_added += 1
                    elif item.media_type == MediaType.TV_SHOW:
                        summary.shows_added += 1
                elif result.status == RequestStatus.SKIPPED:
                    summary.skipped += 1
                elif result.status == RequestStatus.FAILED:
                    summary.failed += 1

        except PlexApiError as e:
            logger.error(f"Failed to fetch Plex watchlist: {e}")
            raise

        # Only log at INFO level if items were added or failed
        items_changed = summary.movies_added + summary.shows_added + summary.failed
        log_level = logger.info if items_changed > 0 else logger.debug
        log_level(
            f"Sync complete: {summary.movies_added} movies, "
            f"{summary.shows_added} shows added, "
            f"{summary.skipped} skipped, {summary.failed} failed"
        )

        return summary

    def _sync_item(self, item: WatchlistItem) -> SyncResult:
        """Sync a single watchlist item.

        Args:
            item: Watchlist item to sync

        Returns:
            SyncResult with outcome
        """
        logger.debug(f"Processing: {item.title} ({item.media_type.value})")

        if item.media_type == MediaType.MOVIE:
            return self._sync_movie(item)
        elif item.media_type == MediaType.TV_SHOW:
            return self._sync_tv_show(item)
        else:
            return SyncResult(
                item=item,
                status=RequestStatus.FAILED,
                message=f"Unsupported media type: {item.media_type}",
                target_service="none",
            )

    def _sync_movie(self, item: WatchlistItem) -> SyncResult:
        """Sync a movie to Radarr.

        Args:
            item: Movie watchlist item

        Returns:
            SyncResult with outcome
        """
        if not self.radarr:
            return SyncResult(
                item=item,
                status=RequestStatus.SKIPPED,
                message="Radarr not configured",
                target_service="radarr",
            )

        if self.database.is_synced(item.rating_key, "radarr"):
            logger.debug(f"  Skipping (already synced): {item.title}")
            return SyncResult(
                item=item,
                status=RequestStatus.SKIPPED,
                message="Already synced to Radarr",
                target_service="radarr",
            )

        # For Letterboxd items, try to resolve TMDB ID lazily
        if item.letterboxd_id and item.letterboxd_slug and not item.provider_ids.tmdb_id:
            # First, check database cache
            cached = self.database.get_letterboxd_metadata(item.letterboxd_id)

            if cached and cached.get("tmdb_id"):
                # Use cached TMDB ID
                item.provider_ids.tmdb_id = cached["tmdb_id"]
                logger.debug(f"  Using cached TMDB ID {item.provider_ids.tmdb_id} for Letterboxd item {item.letterboxd_slug}")
            else:
                # Need to fetch from page
                logger.info(f"  Fetching TMDB ID for Letterboxd item: {item.title} ({item.letterboxd_slug})")
                from .api.letterboxd import LetterboxdApi

                letterboxd = LetterboxdApi()
                tmdb_id = letterboxd.fetch_tmdb_id_from_page(item.letterboxd_slug)

                if tmdb_id:
                    item.provider_ids.tmdb_id = tmdb_id
                    # Store in database for future use
                    self.database.set_letterboxd_metadata(
                        letterboxd_id=item.letterboxd_id,
                        slug=item.letterboxd_slug,
                        title=item.title,
                        year=item.year,
                        tmdb_id=tmdb_id,
                    )
                    logger.info(f"  ✓ Resolved TMDB ID {tmdb_id} for {item.title}")
                else:
                    # Still store the metadata without TMDB ID so we don't keep retrying
                    self.database.set_letterboxd_metadata(
                        letterboxd_id=item.letterboxd_id,
                        slug=item.letterboxd_slug,
                        title=item.title,
                        year=item.year,
                        tmdb_id=None,
                    )

        # Log available IDs before enhancement
        logger.debug(
            f"  IDs before enhancement - TMDB: {item.provider_ids.tmdb_id}, "
            f"IMDB: {item.provider_ids.imdb_id}, TVDB: {item.provider_ids.tvdb_id}"
        )

        # Try to enhance provider IDs using TMDB API
        if self.tmdb and self.tmdb.is_configured():
            original_tmdb_id = item.provider_ids.tmdb_id
            item.provider_ids = self.tmdb.enhance_provider_ids(
                item.provider_ids, "movie"
            )
            if item.provider_ids.tmdb_id and not original_tmdb_id:
                logger.info(f"  ✓ Resolved TMDB ID via IMDB lookup: {item.provider_ids.tmdb_id}")

        # Check if we have TMDB ID after enhancement
        if not item.provider_ids.tmdb_id:
            # Build helpful error message based on what IDs we have
            if item.provider_ids.imdb_id:
                if not self.tmdb or not self.tmdb.is_configured():
                    message = (
                        f"No TMDB ID found - only have IMDB ID ({item.provider_ids.imdb_id}). "
                        "Configure TMDB API key to enable IMDB→TMDB conversion."
                    )
                else:
                    message = (
                        f"No TMDB ID found - IMDB lookup failed for {item.provider_ids.imdb_id}. "
                        "Movie may not be in TMDB database."
                    )
            else:
                message = "No TMDB ID or IMDB ID found - required for Radarr"

            logger.warning(f"  {message}: {item.title}")
            self.database.record_sync(
                rating_key=item.rating_key,
                title=item.title,
                media_type=item.media_type,
                target_service="radarr",
                status=RequestStatus.FAILED,
                imdb_id=item.provider_ids.imdb_id,
                error_message=message,
            )
            return SyncResult(
                item=item,
                status=RequestStatus.FAILED,
                message=message,
                target_service="radarr",
            )

        if self.dry_run:
            logger.info(f"  [DRY RUN] Would add to Radarr: {item.title}")
            return SyncResult(
                item=item,
                status=RequestStatus.SUCCESS,
                message=f"[DRY RUN] Would add to Radarr (TMDB: {item.provider_ids.tmdb_id})",
                target_service="radarr",
            )

        try:
            result = self.radarr.add_movie(
                provider_ids=item.provider_ids,
                title=item.title,
                year=item.year,
            )

            logger.info(f"  {result['message']}")

            self.database.record_sync(
                rating_key=item.rating_key,
                title=item.title,
                media_type=item.media_type,
                target_service="radarr",
                status=RequestStatus.SUCCESS,
                tmdb_id=item.provider_ids.tmdb_id,
                imdb_id=item.provider_ids.imdb_id,
            )

            return SyncResult(
                item=item,
                status=RequestStatus.SUCCESS,
                message=result["message"],
                target_service="radarr",
            )

        except RadarrApiError as e:
            logger.error(f"  Failed to add to Radarr: {e}")
            self.database.record_sync(
                rating_key=item.rating_key,
                title=item.title,
                media_type=item.media_type,
                target_service="radarr",
                status=RequestStatus.FAILED,
                tmdb_id=item.provider_ids.tmdb_id,
                error_message=str(e),
            )
            return SyncResult(
                item=item,
                status=RequestStatus.FAILED,
                message=str(e),
                target_service="radarr",
            )

    def _sync_tv_show(self, item: WatchlistItem) -> SyncResult:
        """Sync a TV show to Sonarr.

        Args:
            item: TV show watchlist item

        Returns:
            SyncResult with outcome
        """
        if not self.sonarr:
            return SyncResult(
                item=item,
                status=RequestStatus.SKIPPED,
                message="Sonarr not configured",
                target_service="sonarr",
            )

        if self.database.is_synced(item.rating_key, "sonarr"):
            logger.debug(f"  Skipping (already synced): {item.title}")
            return SyncResult(
                item=item,
                status=RequestStatus.SKIPPED,
                message="Already synced to Sonarr",
                target_service="sonarr",
            )

        # Log available IDs before enhancement
        logger.debug(
            f"  IDs before enhancement - TVDB: {item.provider_ids.tvdb_id}, "
            f"TMDB: {item.provider_ids.tmdb_id}, IMDB: {item.provider_ids.imdb_id}"
        )

        # Try to enhance provider IDs using TMDB API
        if self.tmdb and self.tmdb.is_configured():
            original_tvdb_id = item.provider_ids.tvdb_id
            item.provider_ids = self.tmdb.enhance_provider_ids(
                item.provider_ids, "show"
            )
            if item.provider_ids.tvdb_id and not original_tvdb_id:
                logger.info(f"  ✓ Resolved TVDB ID via TMDB lookup: {item.provider_ids.tvdb_id}")

        # Check if we have TVDB ID after enhancement
        if not item.provider_ids.tvdb_id:
            # Build helpful error message based on what IDs we have
            if item.provider_ids.tmdb_id or item.provider_ids.imdb_id:
                if not self.tmdb or not self.tmdb.is_configured():
                    available_ids = []
                    if item.provider_ids.tmdb_id:
                        available_ids.append(f"TMDB: {item.provider_ids.tmdb_id}")
                    if item.provider_ids.imdb_id:
                        available_ids.append(f"IMDB: {item.provider_ids.imdb_id}")
                    message = (
                        f"No TVDB ID found - have {', '.join(available_ids)}. "
                        "Configure TMDB API key to enable ID conversion."
                    )
                else:
                    message = (
                        f"No TVDB ID found - TMDB lookup failed. "
                        "Show may not be in TMDB/TVDB database."
                    )
            else:
                message = "No TVDB ID found - required for Sonarr"

            logger.warning(f"  {message}: {item.title}")
            self.database.record_sync(
                rating_key=item.rating_key,
                title=item.title,
                media_type=item.media_type,
                target_service="sonarr",
                status=RequestStatus.FAILED,
                tmdb_id=item.provider_ids.tmdb_id,
                imdb_id=item.provider_ids.imdb_id,
                error_message=message,
            )
            return SyncResult(
                item=item,
                status=RequestStatus.FAILED,
                message=message,
                target_service="sonarr",
            )

        if self.dry_run:
            logger.info(f"  [DRY RUN] Would add to Sonarr: {item.title}")
            return SyncResult(
                item=item,
                status=RequestStatus.SUCCESS,
                message=f"[DRY RUN] Would add to Sonarr (TVDB: {item.provider_ids.tvdb_id})",
                target_service="sonarr",
            )

        try:
            result = self.sonarr.add_series(
                provider_ids=item.provider_ids,
                title=item.title,
            )

            logger.info(f"  {result['message']}")

            self.database.record_sync(
                rating_key=item.rating_key,
                title=item.title,
                media_type=item.media_type,
                target_service="sonarr",
                status=RequestStatus.SUCCESS,
                tvdb_id=item.provider_ids.tvdb_id,
                tmdb_id=item.provider_ids.tmdb_id,
                imdb_id=item.provider_ids.imdb_id,
            )

            return SyncResult(
                item=item,
                status=RequestStatus.SUCCESS,
                message=result["message"],
                target_service="sonarr",
            )

        except SonarrApiError as e:
            logger.error(f"  Failed to add to Sonarr: {e}")
            self.database.record_sync(
                rating_key=item.rating_key,
                title=item.title,
                media_type=item.media_type,
                target_service="sonarr",
                status=RequestStatus.FAILED,
                tvdb_id=item.provider_ids.tvdb_id,
                error_message=str(e),
            )
            return SyncResult(
                item=item,
                status=RequestStatus.FAILED,
                message=str(e),
                target_service="sonarr",
            )
