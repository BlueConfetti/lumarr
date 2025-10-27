"""Display layer for CLI output."""

from .console import console
from .formatters import format_sync_results
from .tables import (
    create_history_table,
    create_letterboxd_results_table,
    create_service_info_table,
    create_sync_results_table,
    create_watchlist_table,
)

__all__ = [
    "console",
    "format_sync_results",
    "create_sync_results_table",
    "create_letterboxd_results_table",
    "create_history_table",
    "create_watchlist_table",
    "create_service_info_table",
]
