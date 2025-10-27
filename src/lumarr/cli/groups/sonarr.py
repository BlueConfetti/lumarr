"""Sonarr command group."""

import sys

import click

from ...api.sonarr import SonarrApi, SonarrApiError
from ..display import console, create_service_info_table


@click.group('sonarr')
def sonarr_group():
    """Sonarr configuration and management commands."""
    pass


@sonarr_group.command('info')
@click.option(
    "--url",
    help="Sonarr URL (overrides config)",
)
@click.option(
    "--api-key",
    help="Sonarr API key (overrides config)",
)
@click.pass_context
def sonarr_info(ctx, url, api_key):
    """Show Sonarr configuration information (quality profiles, root folders, tags)."""
    config = ctx.obj.config

    sonarr_url = url or config.get("sonarr.url")
    sonarr_api_key = api_key or config.get("sonarr.api_key")

    if not sonarr_url or not sonarr_api_key:
        console.print(
            "[red]Error:[/red] Sonarr URL and API key required.\n"
            "Provide via --url and --api-key flags or configure in config.yaml"
        )
        sys.exit(1)

    try:
        sonarr_api = SonarrApi(
            url=sonarr_url,
            api_key=sonarr_api_key,
            quality_profile=1,
            root_folder="/",
        )

        console.print("[cyan]Connecting to Sonarr...[/cyan]")
        if not sonarr_api.test_connection():
            console.print("[red]Failed to connect to Sonarr. Check your URL and API key.[/red]")
            sys.exit(1)

        console.print(f"[green]✓[/green] Connected to Sonarr at {sonarr_url}\n")

        # Get and display quality profiles
        quality_profiles = sonarr_api.get_quality_profiles()
        console.print("[bold cyan]Quality Profiles[/bold cyan]")
        console.print("[dim]Use these IDs for the 'quality_profile' setting in config.yaml[/dim]\n")

        profiles_table, _, _ = create_service_info_table(profiles=quality_profiles)
        if profiles_table:
            console.print(profiles_table)
        else:
            console.print("[yellow]No quality profiles found[/yellow]")

        console.print()

        # Get and display root folders
        root_folders = sonarr_api.get_root_folders()
        console.print("[bold cyan]Root Folders[/bold cyan]")
        console.print("[dim]Use these paths for the 'root_folder' setting in config.yaml[/dim]\n")

        _, folders_table, _ = create_service_info_table(folders=root_folders)
        if folders_table:
            console.print(folders_table)
        else:
            console.print("[yellow]No root folders found[/yellow]")

        console.print()

        # Get and display tags
        tags = sonarr_api.get_tags()
        if tags:
            console.print("[bold cyan]Tags[/bold cyan]")
            console.print("[dim]Available tags for advanced configuration[/dim]\n")

            _, _, tags_table = create_service_info_table(tags=tags)
            if tags_table:
                console.print(tags_table)
            console.print()

    except SonarrApiError as e:
        console.print(f"[red]Sonarr API Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
