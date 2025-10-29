"""History command - show sync history."""

from pathlib import Path

import rich_click as click

from ..core import with_database
from ..display import console, _render_history_table


@click.command()
@click.option(
    "--limit",
    "-n",
    default=100,
    help="Number of recent records to show",
    show_default=True,
)
@with_database
def history(database, limit):
    """Show sync history."""
    db_path = Path(database.db_path) if hasattr(database, 'db_path') else None

    if db_path and not db_path.exists():
        console.print("[yellow]No sync history found. Run 'lumarr sync' first.[/yellow]")
        return

    records = database.get_sync_history(limit=limit)

    if not records:
        console.print("[yellow]No sync history found.[/yellow]")
        return

    table = _render_history_table(records, limit)
    console.print(table)


# Export for lazy loading
cli = history
