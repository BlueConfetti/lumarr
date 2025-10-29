"""Table builders for CLI output.

Following mtm design patterns:
- Functions named _render_*_table() for consistency
- Header style: "bold cyan"
- Primary column (first) styled as "bold"
- Sorted output where applicable
"""

from rich.table import Table

from ...models import RequestStatus


def _render_sync_results_table(results, title="Sync Results"):
    """
    Create table for Plex sync results.

    Args:
        results: List of SyncResult objects
        title: Table title

    Returns:
        Rich Table object
    """
    table = Table(title=title, header_style="bold cyan")
    table.add_column("Title", style="bold")
    table.add_column("Type")
    table.add_column("Service")
    table.add_column("Status")
    table.add_column("Message")

    for result in results:
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

    return table


def _render_letterboxd_results_table(results, title="Letterboxd Sync Results"):
    """
    Create table for Letterboxd sync results.

    Args:
        results: List of result dictionaries
        title: Table title

    Returns:
        Rich Table object
    """
    table = Table(title=title, header_style="bold cyan")
    table.add_column("Title", style="bold")
    table.add_column("Year")
    table.add_column("Service")
    table.add_column("Status")
    table.add_column("Message")

    for result in results:
        status_style = {
            RequestStatus.SUCCESS: "green",
            RequestStatus.FAILED: "red",
            RequestStatus.SKIPPED: "yellow",
        }.get(result["status"], "white")

        table.add_row(
            result["item"].title,
            str(result["item"].year) if result["item"].year else "N/A",
            "radarr",
            f"[{status_style}]{result['status'].value.upper()}[/{status_style}]",
            result["message"],
        )

    return table


def _render_history_table(records, limit):
    """
    Create table for sync history.

    Args:
        records: List of history records from database
        limit: Number of records shown

    Returns:
        Rich Table object
    """
    table = Table(title=f"Recent Sync History (last {limit} records)", header_style="bold cyan")
    table.add_column("Date", style="bold")
    table.add_column("Title")
    table.add_column("Type")
    table.add_column("Service")
    table.add_column("Status")

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

    return table


def _render_watchlist_table(items, detailed=False):
    """
    Create table for Plex watchlist items.

    Args:
        items: List of watchlist items
        detailed: Show detailed view

    Returns:
        Rich Table object or None for detailed view
    """
    if detailed:
        return None  # Detailed view doesn't use tables

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Title", style="bold", no_wrap=False, width=30)
    table.add_column("Type", style="blue", width=6)
    table.add_column("Year", style="green", width=6)
    table.add_column("Rating", style="yellow", width=8)
    table.add_column("Genres", style="magenta", no_wrap=False, width=25)
    table.add_column("IDs", style="white", width=20)

    for item in items:
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

    return table


def _render_service_info_table(profiles=None, folders=None, tags=None):
    """
    Create tables for Sonarr/Radarr service info.

    Args:
        profiles: List of quality profiles
        folders: List of root folders
        tags: List of tags

    Returns:
        Tuple of (profiles_table, folders_table, tags_table)
    """
    profiles_table = folders_table = tags_table = None

    if profiles:
        profiles_table = Table(show_header=True, header_style="bold cyan")
        profiles_table.add_column("ID", style="bold", width=8)
        profiles_table.add_column("Name", style="white")

        for profile in profiles:
            profiles_table.add_row(
                str(profile.get("id", "")),
                profile.get("name", ""),
            )

    if folders:
        folders_table = Table(show_header=True, header_style="bold cyan")
        folders_table.add_column("ID", style="bold", width=8)
        folders_table.add_column("Path", style="white")
        folders_table.add_column("Free Space", style="green")

        for folder in folders:
            free_space = folder.get("freeSpace", 0)
            free_space_gb = free_space / (1024**3) if free_space else 0

            folders_table.add_row(
                str(folder.get("id", "")),
                folder.get("path", ""),
                f"{free_space_gb:.1f} GB",
            )

    if tags:
        tags_table = Table(show_header=True, header_style="bold cyan")
        tags_table.add_column("ID", style="bold", width=8)
        tags_table.add_column("Label", style="white")

        for tag in tags:
            tags_table.add_row(
                str(tag.get("id", "")),
                tag.get("label", ""),
            )

    return profiles_table, folders_table, tags_table
