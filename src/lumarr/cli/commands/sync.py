"""Sync command - main synchronization functionality."""

import click

from ...models import RequestStatus
from ..core import with_database, with_plex, with_sonarr, with_radarr, with_tmdb, with_letterboxd, trigger_hook
from ..display import console, format_sync_results
from ..logic import establish_baseline, run_follow_mode, SyncManager
from ..logic.follow_mode import _sync_letterboxd_items


@click.command()
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
    help="Continuously monitor watchlist every few seconds",
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
@with_letterboxd
@with_tmdb(optional=True)
@with_radarr(optional=True)
@with_sonarr(optional=True)
@with_plex
@with_database
def sync(ctx, database, plex, sonarr, radarr, tmdb, letterboxd_resolver, dry_run, force_refresh, follow, ignore_existing, min_rating):
    """Sync Plex watchlist and Letterboxd items to Sonarr and Radarr.

    Automatically syncs Letterboxd movies if configured in config.yaml under
    letterboxd.rss or letterboxd.watchlist.
    """
    config = ctx.obj.config

    # Trigger command start hook
    trigger_hook('command_start', command='sync', dry_run=dry_run)

    try:
        if dry_run or config.get("sync.dry_run", False):
            console.print("[yellow]Running in DRY RUN mode - no changes will be made[/yellow]\n")
            dry_run = True

        # Handle --ignore-existing flag: mark all current items as already synced
        if ignore_existing:
            establish_baseline(database, plex, sonarr, radarr, letterboxd_resolver, force_refresh)

            if not follow:
                trigger_hook('command_end', command='sync', success=True)
                return

        # Follow mode: continuous monitoring
        if follow:
            run_follow_mode(
                config, database, plex, sonarr, radarr, tmdb, letterboxd_resolver, dry_run, force_refresh
            )
            trigger_hook('command_end', command='sync', success=True)
            return

        # Single sync mode
        console.print("[cyan]Starting Plex sync...[/cyan]\n")

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

        # Sync Plex watchlist
        plex_summary = sync_manager.sync()

        # Sync Letterboxd if configured
        rss_names = letterboxd_resolver.resolve_rss_usernames()
        watchlist_names = letterboxd_resolver.resolve_watchlist_usernames()

        letterboxd_summary = None
        if (rss_names or watchlist_names) and radarr:
            letterboxd_summary = _sync_letterboxd_items(
                letterboxd_resolver,
                rss_names,
                watchlist_names,
                radarr,
                database,
                sync_manager,
                config,
            )

        # Display results
        format_sync_results(plex_summary, letterboxd_summary)

        # Trigger sync complete hook
        total_added = plex_summary.movies_added + plex_summary.shows_added
        if letterboxd_summary:
            total_added += letterboxd_summary['added']

        trigger_hook(
            'sync_complete',
            total_added=total_added,
            movies_added=plex_summary.movies_added + (letterboxd_summary['added'] if letterboxd_summary else 0),
            shows_added=plex_summary.shows_added,
            failed=plex_summary.failed + (letterboxd_summary['failed'] if letterboxd_summary else 0),
        )

        trigger_hook('command_end', command='sync', success=True)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        trigger_hook('sync_error', error=str(e))
        trigger_hook('command_end', command='sync', success=False, error=str(e))
        raise


# Export for lazy loading
cli = sync
