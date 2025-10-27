"""List command group - list Plex and Letterboxd items."""

import sys

import click
from rich.table import Table

from ...api.letterboxd import LetterboxdApi, LetterboxdApiError
from ..core import with_database, with_plex
from ..display import console, create_watchlist_table


@click.group('list', invoke_without_command=True)
@click.pass_context
def list_group(ctx):
    """List items from Plex watchlist and Letterboxd.

    By default, shows both Plex and Letterboxd items. Use subcommands to show only one source.
    """
    # If no subcommand specified, show both
    if ctx.invoked_subcommand is None:
        # Show Plex section
        console.print("[bold cyan]═══ Plex Watchlist ═══[/bold cyan]\n")
        try:
            ctx.invoke(list_plex, detailed=False, force_refresh=False)
        except Exception as e:
            console.print(f"[red]Plex Error:[/red] {e}")

        # Show Letterboxd section (optional - silently skip if not configured)
        console.print("\n[bold cyan]═══ Letterboxd ═══[/bold cyan]\n")
        try:
            ctx.invoke(
                list_letterboxd,
                rss_usernames=(),
                watchlist_usernames=(),
                min_rating=None,
                detailed=False,
            )
        except Exception:
            # Silently skip if Letterboxd not configured
            console.print("[dim]Not configured (set letterboxd.rss or letterboxd.watchlist in config.yaml)[/dim]")


@list_group.command('plex')
@click.option(
    "--detailed",
    "-d",
    is_flag=True,
    help="Show detailed information including summaries and provider IDs",
)
@click.option(
    "--force-refresh",
    is_flag=True,
    help="Force refresh metadata cache",
)
@click.pass_context
@with_plex
@with_database
def list_plex(ctx, database, plex, detailed, force_refresh):
    """List Plex watchlist items."""
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
        table = create_watchlist_table(watchlist, detailed=False)
        console.print(table)


@list_group.command('letterboxd')
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
    help="Letterboxd username(s) whose watchlists should be fetched. Can be specified multiple times.",
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
def list_letterboxd(ctx, rss_usernames, watchlist_usernames, min_rating, detailed):
    """List movies from Letterboxd."""
    from ..services.letterboxd import LetterboxdResolver

    config = ctx.obj.config
    resolver = LetterboxdResolver(config)

    # CLI parameters take full precedence
    has_cli_params = bool(rss_usernames or watchlist_usernames)

    if has_cli_params:
        rss_names = [*rss_usernames]
        watchlist_names = [*watchlist_usernames]
    else:
        rss_names = resolver.resolve_rss_usernames()
        watchlist_names = resolver.resolve_watchlist_usernames()

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
            items = [item for item in items if item.rating is not None and item.rating >= min_rating]
            skipped = original_count - len(items)
            if skipped > 0:
                console.print(f"[dim]Filtered to ratings ≥ {min_rating:.1f}. Skipped {skipped} item(s).[/dim]")

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
        sys.exit(1)


# Export for lazy loading
cli = list_group
