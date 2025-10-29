"""Display layer for CLI output."""

from .console import console
from .formatters import format_sync_results
from .tables import (
    _render_history_table,
    _render_letterboxd_results_table,
    _render_service_info_table,
    _render_sync_results_table,
    _render_watchlist_table,
)

__all__ = [
    "console",
    "format_sync_results",
    "_render_sync_results_table",
    "_render_letterboxd_results_table",
    "_render_history_table",
    "_render_watchlist_table",
    "_render_service_info_table",
]
