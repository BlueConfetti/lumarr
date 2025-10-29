"""Clear command - clear sync history database."""

from pathlib import Path

import rich_click as click

from ..core import with_database
from ..display import console


@click.command()
@click.confirmation_option(prompt="Are you sure you want to clear all sync history?")
@with_database
def clear(database):
    """Clear sync history database."""
    database.clear_history()
    console.print("[green]✓[/green] Sync history cleared")


# Export for lazy loading
cli = clear
