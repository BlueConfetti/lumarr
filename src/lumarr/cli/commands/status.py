"""Status command - check connection status and show watchlist info."""

from pathlib import Path

import rich_click as click

from ..core import with_database, with_plex, with_sonarr, with_radarr
from ..display import console


@click.command()
@click.pass_context
@with_radarr(optional=True)
@with_sonarr(optional=True)
@with_plex
@with_database
def status(ctx, database, plex, sonarr, radarr):
    """Check connection status and show watchlist info."""
    config = ctx.obj.config

    # Plex status
    watchlist = plex.get_watchlist()
    movies = sum(1 for item in watchlist if item.media_type.value == "movie")
    shows = sum(1 for item in watchlist if item.media_type.value == "show")
    console.print(f"[green]✓[/green] Plex: Connected")
    console.print(f"  Watchlist: {len(watchlist)} items ({movies} movies, {shows} shows)")

    # Sonarr status
    if sonarr:
        console.print(f"\n[green]✓[/green] Sonarr: Connected ({config.get('sonarr.url')})")

    # Radarr status
    if radarr:
        console.print(f"\n[green]✓[/green] Radarr: Connected ({config.get('radarr.url')})")

    # Database status
    db_path = Path(ctx.obj.db_path)
    if db_path.exists():
        records = database.get_sync_history(limit=1000)
        synced_count = sum(1 for r in records if r["status"] == "success")
        console.print(f"\n[cyan]Database:[/cyan] {synced_count} items synced")


# Export for lazy loading
cli = status
