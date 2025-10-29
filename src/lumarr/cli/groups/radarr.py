"""Radarr command group."""

import sys

import rich_click as click

from ...api.radarr import RadarrApi, RadarrApiError
from ..commands.common import normalize_service_url
from ..display import console, _render_service_info_table


@click.group('radarr')
def radarr_group():
    """Radarr configuration and management commands."""
    pass


@radarr_group.command('info')
@click.option(
    "--url",
    help="Radarr URL (overrides config)",
)
@click.option(
    "--api-key",
    help="Radarr API key (overrides config)",
)
@click.pass_context
def radarr_info(ctx, url, api_key):
    """Show Radarr configuration information (quality profiles, root folders, tags)."""
    config = ctx.obj.config

    radarr_url = url or config.get("radarr.url")
    radarr_api_key = api_key or config.get("radarr.api_key")

    if not radarr_url or not radarr_api_key:
        console.print(
            "[red]Error:[/red] Radarr URL and API key required.\n"
            "Provide via --url and --api-key flags or configure in config.yaml"
        )
        sys.exit(1)

    # Normalize URL to handle formats like "192.168.2.2:4019"
    radarr_url = normalize_service_url(radarr_url)

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

        # Get and display quality profiles
        quality_profiles = radarr_api.get_quality_profiles()
        console.print("[bold cyan]Quality Profiles[/bold cyan]")
        console.print("[dim]Use these IDs for the 'quality_profile' setting in config.yaml[/dim]\n")

        profiles_table, _, _ = _render_service_info_table(profiles=quality_profiles)
        if profiles_table:
            console.print(profiles_table)
        else:
            console.print("[yellow]No quality profiles found[/yellow]")

        console.print()

        # Get and display root folders
        root_folders = radarr_api.get_root_folders()
        console.print("[bold cyan]Root Folders[/bold cyan]")
        console.print("[dim]Use these paths for the 'root_folder' setting in config.yaml[/dim]\n")

        _, folders_table, _ = _render_service_info_table(folders=root_folders)
        if folders_table:
            console.print(folders_table)
        else:
            console.print("[yellow]No root folders found[/yellow]")

        console.print()

        # Get and display tags
        tags = radarr_api.get_tags()
        if tags:
            console.print("[bold cyan]Tags[/bold cyan]")
            console.print("[dim]Available tags for advanced configuration[/dim]\n")

            _, _, tags_table = _render_service_info_table(tags=tags)
            if tags_table:
                console.print(tags_table)
            console.print()

    except RadarrApiError as e:
        console.print(f"[red]Radarr API Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
