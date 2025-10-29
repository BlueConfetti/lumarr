"""Plugin loader for lazy command loading, aliases, and global options."""

import importlib
import os
from typing import Optional

import rich_click as click
from rich_click import RichGroup


class LazyCommandGroup(click.Group):
    """Group that loads commands lazily from a directory."""

    def __init__(self, *args, commands_package: str = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.commands_package = commands_package or 'lumarr.cli.commands'

    def list_commands(self, ctx):
        """
        List all available commands by discovering Python files and registered commands.

        Returns:
            List of command names
        """
        rv = []

        # Get lazy-loaded commands from the commands directory
        try:
            package = importlib.import_module(self.commands_package)
            commands_dir = os.path.dirname(package.__file__)

            for filename in os.listdir(commands_dir):
                if filename.endswith('.py') and not filename.startswith('__'):
                    # Remove .py and _cmd suffix if present
                    cmd_name = filename[:-3]
                    if cmd_name.endswith('_cmd'):
                        cmd_name = cmd_name[:-4]
                    rv.append(cmd_name)

        except (ImportError, AttributeError, FileNotFoundError):
            pass

        # Add manually registered commands (like groups)
        if hasattr(self, 'commands') and self.commands:
            for name in self.commands.keys():
                if name not in rv:
                    rv.append(name)

        rv.sort()
        return rv

    def get_command(self, ctx, name):
        """
        Import and return a command by name.

        Args:
            ctx: Click context
            name: Command name

        Returns:
            Click command or None if not found
        """
        # First check if it's a manually registered command (like groups)
        if hasattr(self, 'commands') and name in self.commands:
            return self.commands[name]

        # Try multiple possible module names for lazy-loaded commands
        possible_names = [name, f"{name}_cmd", f"cmd_{name}"]

        for module_name in possible_names:
            try:
                mod = importlib.import_module(f'{self.commands_package}.{module_name}')
                # Try to get 'cli' or the command name as attribute
                cmd = getattr(mod, 'cli', None) or getattr(mod, name, None)
                if cmd:
                    return cmd
            except (ImportError, AttributeError):
                continue

        return None


class AliasedGroup(click.Group):
    """Group that supports command aliases."""

    def __init__(self, *args, aliases: Optional[dict] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.aliases = aliases or {
            'ls': 'list',
            'rm': 'clear',
            'st': 'status',
            'hist': 'history',
        }

    def get_command(self, ctx, cmd_name):
        """
        Get command by name, resolving aliases.

        Args:
            ctx: Click context
            cmd_name: Command name or alias

        Returns:
            Click command or None
        """
        # Resolve alias if it exists
        resolved_name = self.aliases.get(cmd_name, cmd_name)
        return super().get_command(ctx, resolved_name)

    def format_commands(self, ctx, formatter):
        """
        Format commands for help output, including aliases.

        Args:
            ctx: Click context
            formatter: Help formatter
        """
        commands = []
        for subcommand in self.list_commands(ctx):
            cmd = self.get_command(ctx, subcommand)
            if cmd is None:
                continue

            # Find aliases for this command
            aliases = [alias for alias, target in self.aliases.items() if target == subcommand]
            if aliases:
                subcommand = f"{subcommand} ({', '.join(aliases)})"

            help_text = cmd.get_short_help_str(limit=formatter.width)
            commands.append((subcommand, help_text))

        if commands:
            with formatter.section('Commands'):
                formatter.write_dl(commands)


def _store_global_option(ctx, param, value):
    """
    Callback to store global option values in parent context.

    This callback is only for side effects (storing in parent context).
    The actual value handling is done by expose_value=False.
    """
    if value is not None and not ctx.resilient_parsing:
        # Find the root context (main cli group)
        root_ctx = ctx
        while root_ctx.parent is not None:
            root_ctx = root_ctx.parent

        # Store value in root context's params for main cli() to process
        if param.name not in root_ctx.params:
            root_ctx.params[param.name] = value


class LumarrGroup(LazyCommandGroup, AliasedGroup, RichGroup):
    """
    Combined group with lazy loading, aliases, and global options support.

    This is the main group class used for the Lumarr CLI,
    combining lazy command loading, command aliases, global options,
    and rich-click formatting for beautiful help output.
    """

    # Define global options that will be available on all subcommands
    # expose_value=False prevents values from being passed to command functions
    # is_eager=True ensures they're processed early
    # The callback stores values in parent context for main cli() to use
    GLOBAL_OPTIONS = [
        click.Option(
            ['-c', '--config'],
            default=None,
            help='Path to config file (or set LUMARR_CONFIG)',
            expose_value=False,
            is_eager=True,
            callback=_store_global_option,
        ),
        click.Option(
            ['--db'],
            default=None,
            help='Path to database file (or set LUMARR_DB)',
            expose_value=False,
            is_eager=True,
            callback=_store_global_option,
        ),
    ]

    def __init__(self, *args, commands_package: str = None, aliases: Optional[dict] = None, **kwargs):
        # Initialize both parent classes
        LazyCommandGroup.__init__(self, *args, commands_package=commands_package, **kwargs)
        AliasedGroup.__init__(self, *args, aliases=aliases, **kwargs)

    def get_command(self, ctx, cmd_name):
        """Get command with alias resolution, lazy loading, and global options."""
        # First resolve alias
        resolved_name = self.aliases.get(cmd_name, cmd_name)
        # Then lazy load
        cmd = LazyCommandGroup.get_command(self, ctx, resolved_name)

        # Inject global options into the command
        if cmd is not None:
            cmd = self._add_global_options(cmd)

        return cmd

    def _add_global_options(self, cmd):
        """
        Add global options to a command if not already present.

        Args:
            cmd: Click command to add options to

        Returns:
            Command with global options added
        """
        for global_opt in self.GLOBAL_OPTIONS:
            # Check if option already exists on the command
            option_exists = any(
                p.name == global_opt.name for p in cmd.params
            )

            if not option_exists:
                # Insert at beginning so they appear after command-specific options in help
                cmd.params.insert(0, global_opt)

        # RichGroup handles formatting automatically - no need to override
        return cmd

    # Let RichGroup handle formatting - it provides beautiful output by default
