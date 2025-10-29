"""Lumarr CLI - Command-line interface for syncing Plex watchlists."""

import os
import sys

# Configure rich-click BEFORE importing click
import rich_click as click
from rich_click import RichGroup

# Enable rich-click formatting
click.rich_click.USE_RICH_MARKUP = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.MAX_WIDTH = 100

from .. import __version__
from ..config import ConfigError, setup_logging
from .core import LumarrContext, LumarrGroup, get_hook_manager
from .display.console import console


@click.group(
    cls=LumarrGroup,
    commands_package='lumarr.cli.commands',
    context_settings=dict(
        auto_envvar_prefix='LUMARR',
        help_option_names=['-h', '--help'],
    ),
)
@click.version_option(version=__version__, help='Show the version and exit.')
@click.option(
    '-c',
    '--config',
    default=None,
    help='Path to config file (or set LUMARR_CONFIG)',
)
@click.option(
    '--db',
    default=None,
    help='Path to database file (or set LUMARR_DB)',
)
@click.pass_context
def cli(ctx, config, db):
    """Sync Plex watchlist with Sonarr and Radarr."""

    ctx.ensure_object(dict)

    # Resolve config path: CLI > env var > default
    config_path = config or os.environ.get('LUMARR_CONFIG', 'config.yaml')

    # Skip config loading for commands that don't need it
    if ctx.invoked_subcommand in ['config', 'version']:
        ctx.obj = type('obj', (object,), {'config_path': config_path})()
        return

    try:
        # Create application context
        lumarr_ctx = LumarrContext.create(config_path, db)

        # Resolve database path: CLI > env var > config > default
        lumarr_ctx.db_path = (
            db
            or os.environ.get('LUMARR_DB')
            or lumarr_ctx.config.get('sync.database')
            or './lumarr.db'
        )

        # Store context
        ctx.obj = lumarr_ctx

        # Setup logging
        setup_logging(lumarr_ctx.config)

        # Load hooks from config
        hook_manager = get_hook_manager()
        hook_manager.load_from_config(lumarr_ctx.config)

    except ConfigError as e:
        console.print(f"[red]Configuration Error:[/red] {e}")
        console.print(f"\n[cyan]Tip:[/cyan] Run 'lumarr config' to set up your configuration interactively.")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


# Import and register command groups
# These are imported here so they register with the main cli group
from .groups import radarr, sonarr  # noqa: E402, F401

# Add command groups
cli.add_command(sonarr.sonarr_group)
cli.add_command(radarr.radarr_group)


if __name__ == '__main__':
    cli()
