"""Baseline establishment logic for --ignore-existing flag."""

import builtins
import logging

from ...api.letterboxd import LetterboxdApi, LetterboxdApiError
from ...models import MediaType, RequestStatus
from ..display.console import console

logger = logging.getLogger(__name__)


def establish_baseline(database, plex, sonarr, radarr, letterboxd_resolver, force_refresh=False):
    """
    Mark all current watchlist items as already synced (baseline).

    This is used with the --ignore-existing flag to prevent syncing
    items that were already in the watchlist before lumarr was started.

    Args:
        database: Database instance
        plex: Plex API instance
        sonarr: Sonarr API instance (or None)
        radarr: Radarr API instance (or None)
        letterboxd_resolver: LetterboxdResolver instance
        force_refresh: Force refresh Plex cache

    Returns:
        dict: Summary of baseline establishment with counts
    """
    console.print("[yellow]Marking all current items as already synced (baseline)...[/yellow]\n")

    summary = {
        "plex_marked": 0,
        "plex_already_synced": 0,
        "plex_skipped": 0,
        "plex_total": 0,
        "letterboxd_marked": 0,
        "letterboxd_already_synced": 0,
        "letterboxd_total": 0,
    }

    # Process Plex watchlist
    console.print("[cyan]Processing Plex watchlist...[/cyan]")
    watchlist = plex.get_watchlist(force_refresh=force_refresh)
    summary["plex_total"] = len(watchlist)

    for item in watchlist:
        # Determine target service based on media type
        if item.media_type == MediaType.MOVIE and radarr:
            target_service = "radarr"
        elif item.media_type == MediaType.TV_SHOW and sonarr:
            target_service = "sonarr"
        else:
            summary["plex_skipped"] += 1
            continue

        # Mark as synced if not already marked
        if not database.is_synced(item.rating_key, target_service):
            database.record_sync(
                rating_key=item.rating_key,
                title=item.title,
                media_type=item.media_type,
                target_service=target_service,
                status=RequestStatus.SUCCESS,
                tmdb_id=item.provider_ids.tmdb_id,
                tvdb_id=item.provider_ids.tvdb_id,
                imdb_id=item.provider_ids.imdb_id,
            )
            summary["plex_marked"] += 1
        else:
            summary["plex_already_synced"] += 1

    console.print(
        f"  Plex: Marked {summary['plex_marked']} new, "
        f"{summary['plex_already_synced']} already synced, "
        f"{summary['plex_total']} total"
    )

    # Process Letterboxd items
    rss_names = letterboxd_resolver.resolve_rss_usernames()
    watchlist_names = letterboxd_resolver.resolve_watchlist_usernames()

    if (rss_names or watchlist_names) and radarr:
        console.print("[cyan]Processing Letterboxd items...[/cyan]")
        try:
            letterboxd = LetterboxdApi(
                usernames=rss_names,
                watchlist_usernames=watchlist_names,
            )

            lbox_items = []
            if rss_names:
                lbox_items.extend(letterboxd.get_watched_movies(rss_names))
            if watchlist_names:
                lbox_items.extend(letterboxd.get_watchlist_movies(watchlist_names))

            # Deduplicate
            unique_lbox = {}
            for item in lbox_items:
                unique_lbox[item.rating_key] = item
            lbox_items = builtins.list(unique_lbox.values())

            summary["letterboxd_total"] = len(lbox_items)

            for item in lbox_items:
                # Store Letterboxd metadata without fetching TMDB ID
                if item.letterboxd_id and item.letterboxd_slug:
                    database.set_letterboxd_metadata(
                        letterboxd_id=item.letterboxd_id,
                        slug=item.letterboxd_slug,
                        title=item.title,
                        year=item.year,
                        tmdb_id=None,  # Don't fetch during baseline
                    )

                if not database.is_synced(item.rating_key, "radarr"):
                    database.record_sync(
                        rating_key=item.rating_key,
                        title=item.title,
                        media_type=MediaType.MOVIE,
                        target_service="radarr",
                        status=RequestStatus.SUCCESS,
                        tmdb_id=None,  # No TMDB ID during baseline
                        imdb_id=None,
                    )
                    summary["letterboxd_marked"] += 1
                else:
                    summary["letterboxd_already_synced"] += 1

            console.print(
                f"  Letterboxd: Marked {summary['letterboxd_marked']} new, "
                f"{summary['letterboxd_already_synced']} already synced, "
                f"{summary['letterboxd_total']} total"
            )

        except LetterboxdApiError as e:
            console.print(f"  [yellow]Warning:[/yellow] Could not fetch Letterboxd items: {e}")

    console.print(f"\n[green]✓[/green] Baseline established")
    console.print("[dim]Future syncs will only process new additions[/dim]\n")

    return summary
