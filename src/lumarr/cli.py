"""Command-line interface for lumarr."""

import builtins
import logging
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from . import __version__
from .api.letterboxd import LetterboxdApi, LetterboxdApiError
from .api.plex import PlexApi, PlexApiError
from .api.radarr import RadarrApi, RadarrApiError
from .api.sonarr import SonarrApi, SonarrApiError
from .api.tmdb import TmdbApi
from .config import Config, ConfigError, setup_logging
from .config_wizard import ConfigWizard
from .db import Database
from .models import MediaType, RequestStatus
from .sync import SyncManager

console = Console()
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version=__version__)
@click.option(
    "--config",
    "-c",
    default=None,
    help="Path to config file",
)
@click.option(
    "--db",
    default=None,
    help="Path to database file",
)
@click.pass_context
def main(ctx, config, db):
    """Sync Plex watchlist with Sonarr and Radarr."""

    ctx.ensure_object(dict)

    # Resolve config path: CLI > env var > default
    config_path = config or os.environ.get("LUMARR_CONFIG", "config.yaml")
    ctx.obj["config_path"] = config_path

    # Don't require config for the 'config' command itself
    if ctx.invoked_subcommand == "config":
        return

    try:
        ctx.obj["config"] = Config(config_path)
        setup_logging(ctx.obj["config"])

        # Resolve database path: CLI > env var > config > default
        db_path = (
            db
            or os.environ.get("LUMARR_DB")
            or ctx.obj["config"].get("sync.database")
            or "./lumarr.db"
        )
        ctx.obj["db_path"] = db_path

    except ConfigError as e:
        console.print(f"[red]Configuration Error:[/red] {e}")
        console.print(f"\n[cyan]Tip:[/cyan] Run 'lumarr config' to set up your configuration interactively.")
        sys.exit(1)


@main.command(name="config")
@click.pass_context
def config_command(ctx):
    """Interactive configuration wizard.

    Launch the interactive configuration wizard to set up or modify
    your lumarr configuration. The wizard will guide you through
    configuring Plex, Sonarr, Radarr, Letterboxd, and other services.
    """
    config_path = ctx.obj.get("config_path", "config.yaml")

    try:
        wizard = ConfigWizard(config_path)
        wizard.run()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Configuration cancelled.[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        logger.exception("Error in configuration wizard")
        sys.exit(1)


@main.command()
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview changes without making them",
)
@click.option(
    "--force-refresh",
    is_flag=True,
    help="Force refresh metadata cache",
)
@click.option(
    "--follow",
    "-f",
    is_flag=True,
    help="Continuously monitor watchlist every 5 seconds",
)
@click.option(
    "--ignore-existing",
    is_flag=True,
    help="Mark all current watchlist items as already synced (baseline)",
)
@click.option(
    "--min-rating",
    type=click.FloatRange(0, 5),
    help="Only sync Letterboxd movies with this rating or higher (0.0-5.0)",
)
@click.pass_context
def sync(ctx, dry_run, force_refresh, follow, ignore_existing, min_rating):
    """Sync Plex watchlist and Letterboxd items to Sonarr and Radarr.

    Automatically syncs Letterboxd movies if configured in config.yaml under
    letterboxd.rss or letterboxd.watchlist.
    """
    config = ctx.obj["config"]

    if dry_run or config.get("sync.dry_run", False):
        console.print("[yellow]Running in DRY RUN mode - no changes will be made[/yellow]\n")
        dry_run = True

    try:
        # Create database first so we can pass it to PlexApi for caching
        db_path = ctx.obj["db_path"]
        database = Database(db_path)
        cache_max_age_days = config.get("sync.cache_max_age_days", 7)
        rss_id = config.get("plex.rss_id")

        plex = PlexApi(
            auth_token=config.get("plex.token"),
            client_identifier=config.get("plex.client_identifier", "lumarr"),
            database=database,
            cache_max_age_days=cache_max_age_days,
            rss_id=rss_id if rss_id else None,
        )

        console.print("[cyan]Testing Plex connection...[/cyan]")
        if not plex.ping():
            console.print("[red]Failed to connect to Plex. Check your token.[/red]")
            sys.exit(1)
        console.print("[green]✓[/green] Plex connection successful\n")

        sonarr = None
        if config.get("sonarr.enabled", False):
            console.print("[cyan]Testing Sonarr connection...[/cyan]")
            sonarr = SonarrApi(
                url=config.get("sonarr.url"),
                api_key=config.get("sonarr.api_key"),
                quality_profile=config.get("sonarr.quality_profile", 1),
                root_folder=config.get("sonarr.root_folder"),
                series_type=config.get("sonarr.series_type", "standard"),
                season_folder=config.get("sonarr.season_folder", True),
                monitor_all=config.get("sonarr.monitor_all", False),
            )
            if not sonarr.test_connection():
                console.print("[red]Failed to connect to Sonarr. Check your URL and API key.[/red]")
                sys.exit(1)
            console.print("[green]✓[/green] Sonarr connection successful\n")

        radarr = None
        if config.get("radarr.enabled", False):
            console.print("[cyan]Testing Radarr connection...[/cyan]")
            radarr = RadarrApi(
                url=config.get("radarr.url"),
                api_key=config.get("radarr.api_key"),
                quality_profile=config.get("radarr.quality_profile", 1),
                root_folder=config.get("radarr.root_folder"),
                monitored=config.get("radarr.monitored", True),
                search_on_add=config.get("radarr.search_on_add", True),
            )
            if not radarr.test_connection():
                console.print("[red]Failed to connect to Radarr. Check your URL and API key.[/red]")
                sys.exit(1)
            console.print("[green]✓[/green] Radarr connection successful\n")

        tmdb_key = config.get("tmdb.api_key")
        tmdb = TmdbApi(api_key=tmdb_key) if tmdb_key else None
        if tmdb and tmdb.is_configured():
            console.print("[green]✓[/green] TMDB API configured\n")

        # Handle --ignore-existing flag: mark all current items as already synced
        if ignore_existing:
            console.print("[yellow]Marking all current items as already synced (baseline)...[/yellow]\n")

            # Process Plex watchlist
            console.print("[cyan]Processing Plex watchlist...[/cyan]")
            watchlist = plex.get_watchlist(force_refresh=force_refresh)

            plex_marked = 0
            plex_already_synced = 0
            plex_skipped = 0

            for item in watchlist:
                # Determine target service based on media type
                if item.media_type == MediaType.MOVIE and radarr:
                    target_service = "radarr"
                elif item.media_type == MediaType.TV_SHOW and sonarr:
                    target_service = "sonarr"
                else:
                    plex_skipped += 1
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
                    plex_marked += 1
                else:
                    plex_already_synced += 1

            console.print(f"  Plex: Marked {plex_marked} new, {plex_already_synced} already synced, {len(watchlist)} total")

            # Process Letterboxd items
            rss_names = _resolve_letterboxd_usernames(config, ())
            watchlist_names = _resolve_letterboxd_watchlists(config, ())

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

                    lbox_marked = 0
                    lbox_already_synced = 0

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
                            lbox_marked += 1
                        else:
                            lbox_already_synced += 1

                    console.print(f"  Letterboxd: Marked {lbox_marked} new, {lbox_already_synced} already synced, {len(lbox_items)} total")

                except LetterboxdApiError as e:
                    console.print(f"  [yellow]Warning:[/yellow] Could not fetch Letterboxd items: {e}")

            console.print(f"\n[green]✓[/green] Baseline established")
            console.print("[dim]Future syncs will only process new additions[/dim]\n")

            if not follow:
                # Exit early if not in follow mode
                return

        sync_manager = SyncManager(
            plex=plex,
            database=database,
            sonarr=sonarr,
            radarr=radarr,
            tmdb=tmdb,
            dry_run=dry_run,
            force_refresh=force_refresh,
        )

        # Helper function to sync Letterboxd items
        def sync_letterboxd_items():
            """Sync Letterboxd movies to Radarr if configured."""
            logger.debug("sync_letterboxd_items: Starting")
            # Check if Letterboxd is configured
            rss_names = _resolve_letterboxd_usernames(config, ())
            logger.debug(f"sync_letterboxd_items: rss_names = {rss_names}")
            watchlist_names = _resolve_letterboxd_watchlists(config, ())
            logger.debug(f"sync_letterboxd_items: watchlist_names = {watchlist_names}")

            if not rss_names and not watchlist_names:
                return None  # No Letterboxd configured

            # Check if Radarr is enabled
            if not radarr:
                console.print("\n[yellow]Letterboxd configured but Radarr is disabled - skipping Letterboxd sync[/yellow]")
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

                # Apply min_rating filter (CLI takes precedence over config)
                effective_min_rating = min_rating if min_rating is not None else config.get("letterboxd.min_rating", 0)
                if effective_min_rating and effective_min_rating > 0:
                    original_count = len(items)
                    items = [
                        item for item in items
                        if item.rating is not None and item.rating >= effective_min_rating
                    ]
                    filtered = original_count - len(items)
                    if filtered > 0:
                        logger.debug(f"Filtered {filtered} Letterboxd items below rating {effective_min_rating}")

                # Deduplicate items
                unique_items = {}
                for item in items:
                    unique_items[item.rating_key] = item
                items = builtins.list(unique_items.values())

                if not items:
                    return None

                # Sync items
                lbox_summary = {
                    "total": len(items),
                    "added": 0,
                    "skipped": 0,
                    "failed": 0,
                    "results": []
                }

                for item in items:
                    # Check if already synced
                    if database.is_synced(item.rating_key, "radarr"):
                        lbox_summary["skipped"] += 1
                        lbox_summary["results"].append({
                            "item": item,
                            "status": RequestStatus.SKIPPED,
                            "message": "Already synced"
                        })
                        continue

                    # Sync to Radarr using SyncManager's method
                    result = sync_manager._sync_movie(item)
                    lbox_summary["results"].append({
                        "item": item,
                        "status": result.status,
                        "message": result.message
                    })

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

        # Helper function for status line updates
        def update_status_line(message):
            """Update status line in place using ANSI codes."""
            # \r = carriage return, \033[K = clear to end of line
            sys.stdout.write(f"\r\033[K{message}")
            sys.stdout.flush()

        # Helper function to run Plex sync only
        def run_plex_sync(show_full_output=False):
            """Sync only Plex items."""
            logger.debug("Checking Plex watchlist...")
            summary = sync_manager.sync()

            if not show_full_output:
                # Quiet mode - only return results if items were added
                if summary.movies_added > 0 or summary.shows_added > 0:
                    return summary
                return None

            return summary

        # Helper function to run Letterboxd sync only
        def run_letterboxd_sync(show_full_output=False):
            """Sync only Letterboxd items."""
            logger.debug("Checking Letterboxd...")
            lbox_summary = sync_letterboxd_items()

            if not show_full_output:
                # Quiet mode - only return results if items were added
                if lbox_summary and lbox_summary["added"] > 0:
                    return lbox_summary
                return None

            return lbox_summary

        # Helper function to run a full sync (both services)
        def run_sync(show_full_output=True):
            if show_full_output:
                console.print("[cyan]Starting Plex sync...[/cyan]\n")

            summary = sync_manager.sync()

            # Sync Letterboxd items if configured
            lbox_summary = sync_letterboxd_items()

            # In follow mode after first run, only show output if items were added
            if not show_full_output:
                items_added = summary.movies_added + summary.shows_added
                lbox_added = lbox_summary["added"] if lbox_summary else 0
                total_added = items_added + lbox_added

                if total_added == 0:
                    # No items added, just log quietly
                    return summary

                # Items were added, show which ones
                if items_added > 0:
                    console.print(f"\n[green]✓ Added {items_added} Plex item(s):[/green]")
                    for result in summary.results:
                        if result.status == RequestStatus.SUCCESS:
                            console.print(f"  • {result.item.title} ({result.item.media_type.value}) → {result.target_service}")

                if lbox_summary and lbox_added > 0:
                    console.print(f"\n[green]✓ Added {lbox_added} Letterboxd movie(s):[/green]")
                    for result in lbox_summary["results"]:
                        if result["status"] == RequestStatus.SUCCESS:
                            console.print(f"  • {result['item'].title} → radarr")

                # Show any failures too
                total_failed = summary.failed + (lbox_summary["failed"] if lbox_summary else 0)
                if total_failed > 0:
                    console.print(f"\n[red]✗ {total_failed} item(s) failed[/red]")
                    for result in summary.results:
                        if result.status == RequestStatus.FAILED:
                            console.print(f"  • {result.item.title}: {result.message}")
                    if lbox_summary:
                        for result in lbox_summary["results"]:
                            if result["status"] == RequestStatus.FAILED:
                                console.print(f"  • {result['item'].title}: {result['message']}")

                return summary

            # Full output mode (first run or non-follow mode)
            # Plex results table
            if summary.results:
                table = Table(title="\nPlex Sync Results")
                table.add_column("Title", style="cyan")
                table.add_column("Type", style="magenta")
                table.add_column("Service", style="blue")
                table.add_column("Status", style="white")
                table.add_column("Message", style="white")

                for result in summary.results:
                    status_style = {
                        RequestStatus.SUCCESS: "green",
                        RequestStatus.FAILED: "red",
                        RequestStatus.SKIPPED: "yellow",
                    }.get(result.status, "white")

                    table.add_row(
                        result.item.title,
                        result.item.media_type.value,
                        result.target_service,
                        f"[{status_style}]{result.status.value.upper()}[/{status_style}]",
                        result.message,
                    )

                console.print(table)

            # Letterboxd results table
            if lbox_summary and lbox_summary["results"]:
                lbox_table = Table(title="\nLetterboxd Sync Results")
                lbox_table.add_column("Title", style="cyan")
                lbox_table.add_column("Year", style="magenta")
                lbox_table.add_column("Service", style="blue")
                lbox_table.add_column("Status", style="white")
                lbox_table.add_column("Message", style="white")

                for result in lbox_summary["results"]:
                    status_style = {
                        RequestStatus.SUCCESS: "green",
                        RequestStatus.FAILED: "red",
                        RequestStatus.SKIPPED: "yellow",
                    }.get(result["status"], "white")

                    lbox_table.add_row(
                        result["item"].title,
                        str(result["item"].year) if result["item"].year else "N/A",
                        "radarr",
                        f"[{status_style}]{result['status'].value.upper()}[/{status_style}]",
                        result["message"],
                    )

                console.print(lbox_table)

            # Combined summary
            console.print(f"\n[bold]Summary:[/bold]")
            console.print(f"  [dim]Plex:[/dim]")
            console.print(f"    Total items: {summary.total}")
            console.print(f"    Movies added: [green]{summary.movies_added}[/green]")
            console.print(f"    Shows added: [green]{summary.shows_added}[/green]")
            console.print(f"    Skipped: [yellow]{summary.skipped}[/yellow]")
            console.print(f"    Failed: [red]{summary.failed}[/red]")

            if lbox_summary:
                console.print(f"  [dim]Letterboxd:[/dim]")
                console.print(f"    Total items: {lbox_summary['total']}")
                console.print(f"    Movies added: [green]{lbox_summary['added']}[/green]")
                console.print(f"    Skipped: [yellow]{lbox_summary['skipped']}[/yellow]")
                console.print(f"    Failed: [red]{lbox_summary['failed']}[/red]")

            return summary

        # Follow mode: continuous monitoring with separate intervals
        if follow:
            # Get sync intervals from config
            plex_interval = config.get("plex.sync_interval", 5)
            lbox_interval = config.get("letterboxd.sync_interval", 30)

            # Check if Letterboxd is configured
            rss_names = _resolve_letterboxd_usernames(config, ())
            watchlist_names = _resolve_letterboxd_watchlists(config, ())
            has_letterboxd = bool((rss_names or watchlist_names) and radarr)

            if has_letterboxd:
                console.print(f"[yellow]Follow mode enabled - checking Plex every {plex_interval}s, Letterboxd every {lbox_interval}s[/yellow]")
            else:
                console.print(f"[yellow]Follow mode enabled - checking Plex every {plex_interval}s[/yellow]")
            console.print("[yellow]Press Ctrl+C to stop[/yellow]\n")

            # Signal handler for graceful shutdown
            shutdown_requested = False
            def signal_handler(_sig, _frame):
                nonlocal shutdown_requested
                shutdown_requested = True
                # Clear status line before showing shutdown message
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
                run_sync(show_full_output=True)
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
                        plex_results = run_plex_sync(show_full_output=False)
                        last_plex_sync = current_time

                        # Show added items with timestamp
                        if plex_results:
                            timestamp = datetime.now().strftime("%H:%M:%S")
                            # Clear status line first
                            sys.stdout.write("\r\033[K")
                            sys.stdout.flush()
                            for result in plex_results.results:
                                if result.status == RequestStatus.SUCCESS:
                                    console.print(f"[{timestamp}] [green]✓[/green] Added: {result.item.title} (Plex) → {result.target_service}")
                    except Exception as e:
                        console.print(f"\r\033[K[red]Error checking Plex:[/red] {e}")
                        logger.exception("Error in Plex sync")

                # Check if Letterboxd needs syncing
                if has_letterboxd and current_time - last_lbox_sync >= lbox_interval:
                    try:
                        lbox_results = run_letterboxd_sync(show_full_output=False)
                        last_lbox_sync = current_time

                        # Show added items with timestamp
                        if lbox_results:
                            timestamp = datetime.now().strftime("%H:%M:%S")
                            # Clear status line first
                            sys.stdout.write("\r\033[K")
                            sys.stdout.flush()
                            for result in lbox_results["results"]:
                                if result["status"] == RequestStatus.SUCCESS:
                                    console.print(f"[{timestamp}] [green]✓[/green] Added: {result['item'].title} (Letterboxd) → radarr")
                    except Exception as e:
                        console.print(f"\r\033[K[red]Error checking Letterboxd:[/red] {e}")
                        logger.exception("Error in Letterboxd sync")

                # Update status line
                if not shutdown_requested:
                    next_plex = max(0, int(plex_interval - (current_time - last_plex_sync)))
                    if has_letterboxd:
                        next_lbox = max(0, int(lbox_interval - (current_time - last_lbox_sync)))
                        update_status_line(f"Monitoring... (Plex in {next_plex}s, Letterboxd in {next_lbox}s)")
                    else:
                        update_status_line(f"Monitoring... (Plex in {next_plex}s)")

                # Sleep for responsiveness to Ctrl+C
                time.sleep(0.5)

            # Clear status line and show stopped message
            sys.stdout.write("\r\033[K")
            sys.stdout.flush()
            console.print("[green]Stopped monitoring.[/green]")

        # Single sync mode
        else:
            run_sync()

    except PlexApiError as e:
        console.print(f"[red]Plex API Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        logger.exception("Unexpected error during sync")
        sys.exit(1)


@main.command()
@click.option(
    "--limit",
    "-n",
    default=100,
    help="Number of recent records to show",
    show_default=True,
)
@click.pass_context
def history(ctx, limit):
    """Show sync history."""
    config = ctx.obj["config"]
    db_path = ctx.obj["db_path"]

    if not Path(db_path).exists():
        console.print("[yellow]No sync history found. Run 'lumarr sync' first.[/yellow]")
        return

    database = Database(db_path)
    records = database.get_sync_history(limit=limit)

    if not records:
        console.print("[yellow]No sync history found.[/yellow]")
        return

    table = Table(title=f"Recent Sync History (last {limit} records)")
    table.add_column("Date", style="cyan")
    table.add_column("Title", style="white")
    table.add_column("Type", style="magenta")
    table.add_column("Service", style="blue")
    table.add_column("Status", style="white")

    for record in records:
        status_style = {
            "success": "green",
            "failed": "red",
            "skipped": "yellow",
        }.get(record["status"], "white")

        synced_at = record["synced_at"].split("T")[0] if "T" in record["synced_at"] else record["synced_at"]

        table.add_row(
            synced_at,
            record["title"],
            record["media_type"],
            record["target_service"],
            f"[{status_style}]{record['status'].upper()}[/{status_style}]",
        )

    console.print(table)


@main.command()
@click.pass_context
def status(ctx):
    """Check connection status and show watchlist info."""
    config = ctx.obj["config"]

    try:
        # Create database for caching
        db_path = ctx.obj["db_path"]
        database = Database(db_path)
        cache_max_age_days = config.get("sync.cache_max_age_days", 7)
        rss_id = config.get("plex.rss_id")

        plex = PlexApi(
            auth_token=config.get("plex.token"),
            client_identifier=config.get("plex.client_identifier", "lumarr"),
            database=database,
            cache_max_age_days=cache_max_age_days,
            rss_id=rss_id if rss_id else None,
        )

        console.print("[cyan]Checking Plex connection...[/cyan]")
        if plex.ping():
            console.print("[green]✓[/green] Plex: Connected")

            watchlist = plex.get_watchlist()
            movies = sum(1 for item in watchlist if item.media_type.value == "movie")
            shows = sum(1 for item in watchlist if item.media_type.value == "show")

            console.print(f"  Watchlist: {len(watchlist)} items ({movies} movies, {shows} shows)")
        else:
            console.print("[red]✗[/red] Plex: Connection failed")

        if config.get("sonarr.enabled", False):
            console.print("\n[cyan]Checking Sonarr connection...[/cyan]")
            sonarr = SonarrApi(
                url=config.get("sonarr.url"),
                api_key=config.get("sonarr.api_key"),
                quality_profile=config.get("sonarr.quality_profile", 1),
                root_folder=config.get("sonarr.root_folder"),
            )
            if sonarr.test_connection():
                console.print(f"[green]✓[/green] Sonarr: Connected ({config.get('sonarr.url')})")
            else:
                console.print(f"[red]✗[/red] Sonarr: Connection failed")

        if config.get("radarr.enabled", False):
            console.print("\n[cyan]Checking Radarr connection...[/cyan]")
            radarr = RadarrApi(
                url=config.get("radarr.url"),
                api_key=config.get("radarr.api_key"),
                quality_profile=config.get("radarr.quality_profile", 1),
                root_folder=config.get("radarr.root_folder"),
            )
            if radarr.test_connection():
                console.print(f"[green]✓[/green] Radarr: Connected ({config.get('radarr.url')})")
            else:
                console.print(f"[red]✗[/red] Radarr: Connection failed")

        db_path = ctx.obj["db_path"]
        if Path(db_path).exists():
            database = Database(db_path)
            records = database.get_sync_history(limit=1000)
            synced_count = sum(1 for r in records if r["status"] == "success")
            console.print(f"\n[cyan]Database:[/cyan] {synced_count} items synced")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.confirmation_option(prompt="Are you sure you want to clear all sync history?")
@click.pass_context
def clear(ctx):
    """Clear sync history database."""
    db_path = ctx.obj["db_path"]

    if not Path(db_path).exists():
        console.print("[yellow]No database found.[/yellow]")
        return

    database = Database(db_path)
    database.clear_history()
    console.print("[green]✓[/green] Sync history cleared")


@main.command()
@click.option(
    "--detailed",
    "-d",
    is_flag=True,
    help="Show detailed information including summaries and provider IDs",
)
@click.option(
    "--debug",
    is_flag=True,
    hidden=True,
    help="Show raw API response (debug mode)",
)
@click.option(
    "--force-refresh",
    is_flag=True,
    help="Force refresh metadata cache",
)
@click.pass_context
def list(ctx, detailed, debug, force_refresh):
    """List all items in your Plex watchlist."""
    config = ctx.obj["config"]

    try:
        # Create database for caching
        db_path = ctx.obj["db_path"]
        database = Database(db_path)
        cache_max_age_days = config.get("sync.cache_max_age_days", 7)
        rss_id = config.get("plex.rss_id")

        plex = PlexApi(
            auth_token=config.get("plex.token"),
            client_identifier=config.get("plex.client_identifier", "lumarr"),
            database=database,
            cache_max_age_days=cache_max_age_days,
            rss_id=rss_id if rss_id else None,
        )

        console.print("[cyan]Connecting to Plex...[/cyan]")
        if not plex.ping():
            console.print("[red]Failed to connect to Plex. Check your token.[/red]")
            sys.exit(1)

        if debug:
            import json
            response = plex.session.get(
                f"{plex.WATCHLIST_URI}/library/sections/watchlist/all",
                headers=plex._get_headers(),
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            console.print("\n[yellow]Initial Watchlist API Response (first item):[/yellow]")
            metadata_list = data.get("MediaContainer", {}).get("Metadata", [])
            console.print(json.dumps(metadata_list[:1], indent=2))

            if metadata_list:
                rating_key = metadata_list[0].get("ratingKey")
                console.print(f"\n[yellow]Fetching detailed metadata for ratingKey: {rating_key}[/yellow]")
                detailed_meta = plex.get_watchlist_metadata(rating_key)
                if detailed_meta:
                    console.print("\n[yellow]Detailed Metadata Response:[/yellow]")
                    console.print(json.dumps(detailed_meta, indent=2))
                else:
                    console.print("[red]Failed to fetch detailed metadata[/red]")
            return

        console.print("[cyan]Fetching watchlist (this may take a moment)...[/cyan]")
        watchlist = plex.get_watchlist(force_refresh=force_refresh)

        if not watchlist:
            console.print("[yellow]Your watchlist is empty.[/yellow]")
            return

        console.print(f"[green]Found {len(watchlist)} items in your watchlist[/green]\n")

        if detailed:
            for item in watchlist:
                console.print(f"[bold cyan]{item.title}[/bold cyan] ({item.year or 'N/A'})")
                console.print(f"  [dim]Type:[/dim] {item.media_type.value}")

                if item.content_rating:
                    console.print(f"  [dim]Rating:[/dim] {item.content_rating}")

                if item.studio:
                    console.print(f"  [dim]Studio:[/dim] {item.studio}")

                if item.genres:
                    console.print(f"  [dim]Genres:[/dim] {', '.join(item.genres)}")

                if item.provider_ids.tmdb_id:
                    console.print(f"  [dim]TMDB ID:[/dim] {item.provider_ids.tmdb_id}")
                if item.provider_ids.tvdb_id:
                    console.print(f"  [dim]TVDB ID:[/dim] {item.provider_ids.tvdb_id}")
                if item.provider_ids.imdb_id:
                    console.print(f"  [dim]IMDB ID:[/dim] {item.provider_ids.imdb_id}")

                if item.summary:
                    summary = item.summary[:200] + "..." if len(item.summary) > 200 else item.summary
                    console.print(f"  [dim]Summary:[/dim] {summary}")

                console.print()
        else:
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Title", style="cyan", no_wrap=False, width=30)
            table.add_column("Type", style="blue", width=6)
            table.add_column("Year", style="green", width=6)
            table.add_column("Rating", style="yellow", width=8)
            table.add_column("Genres", style="magenta", no_wrap=False, width=25)
            table.add_column("IDs", style="white", width=20)

            for item in watchlist:
                genres_str = ", ".join(item.genres[:3]) if item.genres else ""
                if len(item.genres) > 3:
                    genres_str += "..."

                ids = []
                if item.provider_ids.tmdb_id:
                    ids.append(f"TMDB:{item.provider_ids.tmdb_id}")
                if item.provider_ids.tvdb_id:
                    ids.append(f"TVDB:{item.provider_ids.tvdb_id}")
                if item.provider_ids.imdb_id:
                    ids.append(f"IMDB:{item.provider_ids.imdb_id}")
                ids_str = "\n".join(ids) if ids else "N/A"

                table.add_row(
                    item.title,
                    item.media_type.value,
                    str(item.year) if item.year else "N/A",
                    item.content_rating or "N/A",
                    genres_str,
                    ids_str,
                )

            console.print(table)

    except PlexApiError as e:
        console.print(f"[red]Plex API Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        logger.exception("Unexpected error listing watchlist")
        sys.exit(1)


@main.group()
def sonarr():
    """Sonarr configuration and management commands."""
    pass


@sonarr.command()
@click.option(
    "--url",
    help="Sonarr URL (overrides config)",
)
@click.option(
    "--api-key",
    help="Sonarr API key (overrides config)",
)
@click.pass_context
def info(ctx, url, api_key):
    """Show Sonarr configuration information (quality profiles, root folders, tags)."""
    config = ctx.obj["config"]

    sonarr_url = url or config.get("sonarr.url")
    sonarr_api_key = api_key or config.get("sonarr.api_key")

    if not sonarr_url or not sonarr_api_key:
        console.print(
            "[red]Error:[/red] Sonarr URL and API key required.\n"
            "Provide via --url and --api-key flags or configure in config.yaml"
        )
        sys.exit(1)

    try:
        sonarr_api = SonarrApi(
            url=sonarr_url,
            api_key=sonarr_api_key,
            quality_profile=1,
            root_folder="/",
        )

        console.print("[cyan]Connecting to Sonarr...[/cyan]")
        if not sonarr_api.test_connection():
            console.print("[red]Failed to connect to Sonarr. Check your URL and API key.[/red]")
            sys.exit(1)

        console.print(f"[green]✓[/green] Connected to Sonarr at {sonarr_url}\n")

        quality_profiles = sonarr_api.get_quality_profiles()
        console.print("[bold cyan]Quality Profiles[/bold cyan]")
        console.print("[dim]Use these IDs for the 'quality_profile' setting in config.yaml[/dim]\n")

        if quality_profiles:
            profiles_table = Table(show_header=True, header_style="bold magenta")
            profiles_table.add_column("ID", style="cyan", width=8)
            profiles_table.add_column("Name", style="white")

            for profile in quality_profiles:
                profiles_table.add_row(
                    str(profile.get("id", "")),
                    profile.get("name", ""),
                )

            console.print(profiles_table)
        else:
            console.print("[yellow]No quality profiles found[/yellow]")

        console.print()

        root_folders = sonarr_api.get_root_folders()
        console.print("[bold cyan]Root Folders[/bold cyan]")
        console.print("[dim]Use these paths for the 'root_folder' setting in config.yaml[/dim]\n")

        if root_folders:
            folders_table = Table(show_header=True, header_style="bold magenta")
            folders_table.add_column("ID", style="cyan", width=8)
            folders_table.add_column("Path", style="white")
            folders_table.add_column("Free Space", style="green")

            for folder in root_folders:
                free_space = folder.get("freeSpace", 0)
                free_space_gb = free_space / (1024**3) if free_space else 0

                folders_table.add_row(
                    str(folder.get("id", "")),
                    folder.get("path", ""),
                    f"{free_space_gb:.1f} GB",
                )

            console.print(folders_table)
        else:
            console.print("[yellow]No root folders found[/yellow]")

        console.print()

        tags = sonarr_api.get_tags()
        if tags:
            console.print("[bold cyan]Tags[/bold cyan]")
            console.print("[dim]Available tags for advanced configuration[/dim]\n")

            tags_table = Table(show_header=True, header_style="bold magenta")
            tags_table.add_column("ID", style="cyan", width=8)
            tags_table.add_column("Label", style="white")

            for tag in tags:
                tags_table.add_row(
                    str(tag.get("id", "")),
                    tag.get("label", ""),
                )

            console.print(tags_table)
            console.print()

    except SonarrApiError as e:
        console.print(f"[red]Sonarr API Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        logger.exception("Unexpected error fetching Sonarr info")
        sys.exit(1)


@main.group()
def radarr():
    """Radarr configuration and management commands."""
    pass


@radarr.command()
@click.option(
    "--url",
    help="Radarr URL (overrides config)",
)
@click.option(
    "--api-key",
    help="Radarr API key (overrides config)",
)
@click.pass_context
def info(ctx, url, api_key):
    """Show Radarr configuration information (quality profiles, root folders, tags)."""
    config = ctx.obj["config"]

    radarr_url = url or config.get("radarr.url")
    radarr_api_key = api_key or config.get("radarr.api_key")

    if not radarr_url or not radarr_api_key:
        console.print(
            "[red]Error:[/red] Radarr URL and API key required.\n"
            "Provide via --url and --api-key flags or configure in config.yaml"
        )
        sys.exit(1)

    try:
        radarr_api = RadarrApi(
            url=radarr_url,
            api_key=radarr_api_key,
            quality_profile=1,
            root_folder="/",
        )

        console.print("[cyan]Connecting to Radarr...[/cyan]")
        if not radarr_api.test_connection():
            console.print("[red]Failed to connect to Radarr. Check your URL and API key.[/red]")
            sys.exit(1)

        console.print(f"[green]✓[/green] Connected to Radarr at {radarr_url}\n")

        quality_profiles = radarr_api.get_quality_profiles()
        console.print("[bold cyan]Quality Profiles[/bold cyan]")
        console.print("[dim]Use these IDs for the 'quality_profile' setting in config.yaml[/dim]\n")

        if quality_profiles:
            profiles_table = Table(show_header=True, header_style="bold magenta")
            profiles_table.add_column("ID", style="cyan", width=8)
            profiles_table.add_column("Name", style="white")

            for profile in quality_profiles:
                profiles_table.add_row(
                    str(profile.get("id", "")),
                    profile.get("name", ""),
                )

            console.print(profiles_table)
        else:
            console.print("[yellow]No quality profiles found[/yellow]")

        console.print()

        root_folders = radarr_api.get_root_folders()
        console.print("[bold cyan]Root Folders[/bold cyan]")
        console.print("[dim]Use these paths for the 'root_folder' setting in config.yaml[/dim]\n")

        if root_folders:
            folders_table = Table(show_header=True, header_style="bold magenta")
            folders_table.add_column("ID", style="cyan", width=8)
            folders_table.add_column("Path", style="white")
            folders_table.add_column("Free Space", style="green")

            for folder in root_folders:
                free_space = folder.get("freeSpace", 0)
                free_space_gb = free_space / (1024**3) if free_space else 0

                folders_table.add_row(
                    str(folder.get("id", "")),
                    folder.get("path", ""),
                    f"{free_space_gb:.1f} GB",
                )

            console.print(folders_table)
        else:
            console.print("[yellow]No root folders found[/yellow]")

        console.print()

        tags = radarr_api.get_tags()
        if tags:
            console.print("[bold cyan]Tags[/bold cyan]")
            console.print("[dim]Available tags for advanced configuration[/dim]\n")

            tags_table = Table(show_header=True, header_style="bold magenta")
            tags_table.add_column("ID", style="cyan", width=8)
            tags_table.add_column("Label", style="white")

            for tag in tags:
                tags_table.add_row(
                    str(tag.get("id", "")),
                    tag.get("label", ""),
                )

            console.print(tags_table)
            console.print()

    except RadarrApiError as e:
        console.print(f"[red]Radarr API Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        logger.exception("Unexpected error fetching Radarr info")
        sys.exit(1)


@main.group(context_settings=dict(ignore_unknown_options=True, allow_extra_args=True))
@click.pass_context
def lbox(ctx):
    """Letterboxd listing commands.

    Note: To sync Letterboxd items, use 'lumarr sync' command instead.
    Configure Letterboxd usernames in config.yaml under letterboxd.rss or letterboxd.watchlist.
    """
    if ctx.args:
        logger.debug("Ignoring extra CLI args for lbox: %%s", ctx.args)
        ctx.args = []

def _resolve_letterboxd_usernames(config, rss_overrides):
    """Determine Letterboxd usernames from CLI overrides or config."""
    usernames = [*rss_overrides]
    if usernames:
        return usernames

    config_rss = config.get("letterboxd.rss")
    if config_rss:
        if isinstance(config_rss, str):
            return [config_rss]
        if isinstance(config_rss, builtins.list):
            return config_rss
        try:
            return builtins.list(config_rss)
        except TypeError:
            pass

    legacy_usernames = config.get("letterboxd.usernames")
    if legacy_usernames:
        console.print(
            "[yellow]Warning:[/yellow] 'letterboxd.usernames' is deprecated. "
            "Rename it to 'letterboxd.rss' in config.yaml."
        )
        if isinstance(legacy_usernames, str):
            return [legacy_usernames]
        if isinstance(legacy_usernames, builtins.list):
            return legacy_usernames
        try:
            return builtins.list(legacy_usernames)
        except TypeError:
            pass

    return []


def _resolve_letterboxd_watchlists(config, watchlist_overrides):
    """Determine Letterboxd watchlist usernames from CLI overrides or config."""
    usernames = [*watchlist_overrides]
    if usernames:
        return usernames

    config_watchlist = config.get("letterboxd.watchlist", [])
    if isinstance(config_watchlist, str):
        return [config_watchlist]
    if isinstance(config_watchlist, builtins.list):
        return config_watchlist
    try:
        return builtins.list(config_watchlist)
    except TypeError:
        return []

    return []


@lbox.command(name="list")
@click.option(
    "--rss",
    "-r",
    "rss_usernames",
    multiple=True,
    type=str,
    help="Letterboxd username(s) to fetch. Can be specified multiple times.",
)
@click.option(
    "--watchlist",
    "-w",
    "watchlist_usernames",
    multiple=True,
    type=str,
    help="Letterboxd username(s) whose watchlists should be fetched. "
    "Can be specified multiple times.",
)
@click.option(
    "--min-rating",
    type=click.FloatRange(0, 5),
    help="Only include movies with this rating or higher (0.0-5.0).",
)
@click.option(
    "--detailed",
    "-d",
    is_flag=True,
    help="Show detailed information",
)
@click.pass_context
def lbox_list(ctx, rss_usernames, watchlist_usernames, min_rating, detailed):
    """List watched movies from Letterboxd."""
    config = ctx.obj["config"]

    # CLI parameters take full precedence - if any CLI param is provided, ignore config entirely
    has_cli_params = bool(rss_usernames or watchlist_usernames)

    if has_cli_params:
        # Use only CLI parameters, ignore config entirely
        rss_names = [*rss_usernames]
        watchlist_names = [*watchlist_usernames]
    else:
        # No CLI params - fall back to config for both
        rss_names = _resolve_letterboxd_usernames(config, ())
        watchlist_names = _resolve_letterboxd_watchlists(config, ())

    if not rss_names and not watchlist_names:
        console.print("[red]Error:[/red] No Letterboxd usernames configured.")
        console.print(
            "Add usernames via --rss/--watchlist flags or in config.yaml under letterboxd.rss / letterboxd.watchlist"
        )
        sys.exit(1)

    try:
        letterboxd = LetterboxdApi(
            usernames=rss_names,
            watchlist_usernames=watchlist_names,
        )
        items = []

        if rss_names:
            console.print(
                f"[cyan]Fetching watched movies from Letterboxd RSS for: {', '.join(rss_names)}...[/cyan]"
            )
            items.extend(letterboxd.get_watched_movies(rss_names))

        if watchlist_names:
            console.print(
                f"[cyan]Fetching watchlist movies from Letterboxd for: {', '.join(watchlist_names)}...[/cyan]"
            )
            items.extend(letterboxd.get_watchlist_movies(watchlist_names))

        if not items:
            console.print("[yellow]No movies found.[/yellow]")
            return

        if min_rating is not None:
            original_count = len(items)
            items = [
                item for item in items
                if item.rating is not None and item.rating >= min_rating
            ]
            skipped = original_count - len(items)
            if skipped > 0:
                console.print(
                    f"[dim]Filtered to ratings ≥ {min_rating:.1f}. Skipped {skipped} item(s).[/dim]"
                )

        if not items:
            console.print("[yellow]No movies found after applying rating filter.[/yellow]")
            return

        console.print(f"\n[green]Found {len(items)} movie(s)[/green]\n")

        if detailed:
            for item in items:
                console.print(f"[bold cyan]{item.title}[/bold cyan] ({item.year})")
                if item.rating:
                    stars = "★" * int(item.rating) + "☆" * (5 - int(item.rating))
                    console.print(f"  Rating: {stars} ({item.rating}/5.0)")
                if item.provider_ids and item.provider_ids.tmdb_id:
                    console.print(f"  TMDB ID: {item.provider_ids.tmdb_id}")
                if item.summary:
                    console.print(f"  {item.summary}")
                console.print()
        else:
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Title", style="cyan", no_wrap=False)
            table.add_column("Year", style="green", width=6)
            table.add_column("Rating", style="yellow", width=10)
            table.add_column("TMDB ID", style="blue", width=10)

            for item in items:
                rating_str = ""
                if item.rating:
                    stars = "★" * int(item.rating)
                    rating_str = f"{stars} {item.rating}"

                tmdb_id = "-"
                if item.provider_ids and item.provider_ids.tmdb_id:
                    tmdb_id = item.provider_ids.tmdb_id

                table.add_row(
                    item.title,
                    str(item.year) if item.year else "-",
                    rating_str,
                    tmdb_id,
                )

            console.print(table)

    except LetterboxdApiError as e:
        console.print(f"[red]Letterboxd Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        logger.exception("Unexpected error listing Letterboxd movies")
        sys.exit(1)


if __name__ == "__main__":
    main()
