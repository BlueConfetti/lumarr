"""Config command - interactive configuration wizard."""

import sys

import rich_click as click

from ...config_wizard import ConfigWizard
from ..display import console


@click.command('config')
@click.pass_context
def config_command(ctx):
    """Interactive configuration wizard.

    Launch the interactive configuration wizard to set up or modify
    your lumarr configuration. The wizard will guide you through
    configuring Plex, Sonarr, Radarr, Letterboxd, and other services.
    """
    config_path = ctx.obj.config_path if hasattr(ctx.obj, 'config_path') else "config.yaml"

    try:
        wizard = ConfigWizard(config_path)
        wizard.run()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Configuration cancelled.[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        sys.exit(1)


# Export for lazy loading
cli = config_command
