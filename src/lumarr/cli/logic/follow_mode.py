"""Follow mode logic for continuous monitoring."""

import builtins
import logging
import signal
import sys
import time
from datetime import datetime

from ...api.letterboxd import LetterboxdApi, LetterboxdApiError
from ...models import MediaType, RequestStatus
from ..display.console import console
from .sync_manager import SyncManager

logger = logging.getLogger(__name__)


def run_follow_mode(
    config,
    database,
    plex,
    sonarr,
    radarr,
    tmdb,
    letterboxd_resolver,
    dry_run=False,
    force_refresh=False,
):
    """
    Run continuous monitoring mode.

    Args:
        config: Config object
        database: Database instance
        plex: Plex API instance
        sonarr: Sonarr API instance (or None)
        radarr: Radarr API instance (or None)
        tmdb: TMDB API instance (or None)
        letterboxd_resolver: LetterboxdResolver instance
        dry_run: Preview changes without making them
        force_refresh: Force refresh metadata cache
    """
    # Get sync intervals from config
    plex_interval = config.get("plex.sync_interval", 5)
    lbox_interval = config.get("letterboxd.sync_interval", 30)

    # Check if Letterboxd is configured
    rss_names = letterboxd_resolver.resolve_rss_usernames()
    watchlist_names = letterboxd_resolver.resolve_watchlist_usernames()
    has_letterboxd = bool((rss_names or watchlist_names) and radarr)

    # Create sync manager
    sync_manager = SyncManager(
        plex=plex,
        database=database,
        sonarr=sonarr,
        radarr=radarr,
        tmdb=tmdb,
        dry_run=dry_run,
        force_refresh=force_refresh,
    )

    # Display follow mode info
    if has_letterboxd:
        console.print(
            f"[yellow]Follow mode enabled - checking Plex every {plex_interval}s, "
            f"Letterboxd every {lbox_interval}s[/yellow]"
        )
    else:
        console.print(f"[yellow]Follow mode enabled - checking Plex every {plex_interval}s[/yellow]")
    console.print("[yellow]Press Ctrl+C to stop[/yellow]\n")

    # Signal handler for graceful shutdown
    shutdown_requested = False

    def signal_handler(_sig, _frame):
        nonlocal shutdown_requested
        shutdown_requested = True
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()
        console.print("[yellow]Shutdown requested, stopping...[/yellow]")

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run initial full sync
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    console.print(f"[bold cyan]{'='*80}[/bold cyan]")
    console.print(f"[bold]Initial Sync - {timestamp}[/bold]")
    console.print(f"[bold cyan]{'='*80}[/bold cyan]\n")

    try:
        _run_full_sync(
            sync_manager,
            letterboxd_resolver,
            rss_names,
            watchlist_names,
            radarr,
            config,
            show_full_output=True,
        )
    except Exception as e:
        console.print(f"[red]Error during initial sync:[/red] {e}")
        logger.exception("Error in initial sync")

    console.print(f"\n[dim]Monitoring for new items... (Ctrl+C to stop)[/dim]\n")

    # Track last sync times
    last_plex_sync = time.time()
    last_lbox_sync = time.time()

    # Monitoring loop with separate intervals
    while not shutdown_requested:
        current_time = time.time()

        # Check if Plex needs syncing
        if current_time - last_plex_sync >= plex_interval:
            try:
                plex_results = sync_manager.sync()
                last_plex_sync = current_time

                # Show added items with timestamp
                if plex_results.movies_added > 0 or plex_results.shows_added > 0:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    sys.stdout.write("\r\033[K")
                    sys.stdout.flush()
                    for result in plex_results.results:
                        if result.status == RequestStatus.SUCCESS:
                            console.print(
                                f"[{timestamp}] [green]✓[/green] Added: {result.item.title} "
                                f"(Plex) → {result.target_service}"
                            )
            except Exception as e:
                console.print(f"\r\033[K[red]Error checking Plex:[/red] {e}")
                logger.exception("Error in Plex sync")

        # Check if Letterboxd needs syncing
        if has_letterboxd and current_time - last_lbox_sync >= lbox_interval:
            try:
                lbox_results = _sync_letterboxd_items(
                    letterboxd_resolver,
                    rss_names,
                    watchlist_names,
                    radarr,
                    database,
                    sync_manager,
                    config,
                )
                last_lbox_sync = current_time

                # Show added items with timestamp
                if lbox_results and lbox_results["added"] > 0:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    sys.stdout.write("\r\033[K")
                    sys.stdout.flush()
                    for result in lbox_results["results"]:
                        if result["status"] == RequestStatus.SUCCESS:
                            console.print(
                                f"[{timestamp}] [green]✓[/green] Added: {result['item'].title} "
                                f"(Letterboxd) → radarr"
                            )
            except Exception as e:
                console.print(f"\r\033[K[red]Error checking Letterboxd:[/red] {e}")
                logger.exception("Error in Letterboxd sync")

        # Update status line
        if not shutdown_requested:
            next_plex = max(0, int(plex_interval - (current_time - last_plex_sync)))
            if has_letterboxd:
                next_lbox = max(0, int(lbox_interval - (current_time - last_lbox_sync)))
                _update_status_line(f"Monitoring... (Plex in {next_plex}s, Letterboxd in {next_lbox}s)")
            else:
                _update_status_line(f"Monitoring... (Plex in {next_plex}s)")

        # Sleep for responsiveness to Ctrl+C
        time.sleep(0.5)

    # Clear status line and show stopped message
    sys.stdout.write("\r\033[K")
    sys.stdout.flush()
    console.print("[green]Stopped monitoring.[/green]")


def _update_status_line(message):
    """Update status line in place using ANSI codes."""
    sys.stdout.write(f"\r\033[K{message}")
    sys.stdout.flush()


def _sync_letterboxd_items(
    letterboxd_resolver,
    rss_names,
    watchlist_names,
    radarr,
    database,
    sync_manager,
    config,
):
    """Sync Letterboxd movies to Radarr."""
    if not rss_names and not watchlist_names:
        return None

    if not radarr:
        return None

    try:
        letterboxd = LetterboxdApi(
            usernames=rss_names,
            watchlist_usernames=watchlist_names,
        )

        items = []
        if rss_names:
            items.extend(letterboxd.get_watched_movies(rss_names))
        if watchlist_names:
            items.extend(letterboxd.get_watchlist_movies(watchlist_names))

        if not items:
            return None

        # Apply min_rating filter
        min_rating = config.get("letterboxd.min_rating", 0)
        if min_rating and min_rating > 0:
            items = [item for item in items if item.rating is not None and item.rating >= min_rating]

        # Deduplicate items
        unique_items = {}
        for item in items:
            unique_items[item.rating_key] = item
        items = builtins.list(unique_items.values())

        if not items:
            return None

        # Sync items
        lbox_summary = {"total": len(items), "added": 0, "skipped": 0, "failed": 0, "results": []}

        for item in items:
            # Check if already synced
            if database.is_synced(item.rating_key, "radarr"):
                lbox_summary["skipped"] += 1
                lbox_summary["results"].append(
                    {"item": item, "status": RequestStatus.SKIPPED, "message": "Already synced"}
                )
                continue

            # Sync to Radarr
            result = sync_manager._sync_movie(item)
            lbox_summary["results"].append(
                {"item": item, "status": result.status, "message": result.message}
            )

            if result.status == RequestStatus.SUCCESS:
                lbox_summary["added"] += 1
            elif result.status == RequestStatus.SKIPPED:
                lbox_summary["skipped"] += 1
            elif result.status == RequestStatus.FAILED:
                lbox_summary["failed"] += 1

        return lbox_summary

    except LetterboxdApiError as e:
        console.print(f"\n[red]Letterboxd Error:[/red] {e}")
        logger.exception("Error syncing Letterboxd items")
        return None


def _run_full_sync(
    sync_manager,
    letterboxd_resolver,
    rss_names,
    watchlist_names,
    radarr,
    config,
    show_full_output=True,
):
    """Run a full sync of both Plex and Letterboxd."""
    # Sync Plex
    summary = sync_manager.sync()

    # Sync Letterboxd
    lbox_summary = _sync_letterboxd_items(
        letterboxd_resolver,
        rss_names,
        watchlist_names,
        radarr,
        sync_manager.database,
        sync_manager,
        config,
    )

    # Display results if requested
    if show_full_output:
        from ..display.formatters import format_sync_results

        format_sync_results(summary, lbox_summary)
