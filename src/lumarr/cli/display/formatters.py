"""Output formatters for CLI."""

from .console import console
from .tables import create_sync_results_table, create_letterboxd_results_table


def format_sync_results(plex_summary, letterboxd_summary=None):
    """
    Format and display sync results with tables and summary.

    Args:
        plex_summary: Plex sync summary object
        letterboxd_summary: Letterboxd sync summary dict (optional)
    """
    # Plex results table
    if plex_summary.results:
        table = create_sync_results_table(plex_summary.results, title="Plex Sync Results")
        console.print(table)

    # Letterboxd results table
    if letterboxd_summary and letterboxd_summary.get("results"):
        table = create_letterboxd_results_table(
            letterboxd_summary["results"], title="Letterboxd Sync Results"
        )
        console.print(table)

    # Combined summary
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  [dim]Plex:[/dim]")
    console.print(f"    Total items: {plex_summary.total}")
    console.print(f"    Movies added: [green]{plex_summary.movies_added}[/green]")
    console.print(f"    Shows added: [green]{plex_summary.shows_added}[/green]")
    console.print(f"    Skipped: [yellow]{plex_summary.skipped}[/yellow]")
    console.print(f"    Failed: [red]{plex_summary.failed}[/red]")

    if letterboxd_summary:
        console.print(f"  [dim]Letterboxd:[/dim]")
        console.print(f"    Total items: {letterboxd_summary['total']}")
        console.print(f"    Movies added: [green]{letterboxd_summary['added']}[/green]")
        console.print(f"    Skipped: [yellow]{letterboxd_summary['skipped']}[/yellow]")
        console.print(f"    Failed: [red]{letterboxd_summary['failed']}[/red]")
