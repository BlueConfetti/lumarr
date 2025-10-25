"""Interactive configuration wizard for lumarr."""

import logging
import re
import sys
from pathlib import Path
from typing import Any, Callable, Optional, Tuple

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.spinner import Spinner
from rich.syntax import Syntax
from rich.table import Table

from .api.letterboxd import LetterboxdApi
from .api.plex import PlexApi
from .api.radarr import RadarrApi
from .api.sonarr import SonarrApi
from .api.tmdb import TmdbApi
from .db import Database

console = Console()
logger = logging.getLogger(__name__)


class ConfigWizard:
    """Interactive configuration wizard."""

    def __init__(self, config_path: str):
        """Initialize configuration wizard.

        Args:
            config_path: Path to config file
        """
        self.config_path = Path(config_path)
        self.config_data = {}
        self.changes_made = False

    def run(self):
        """Run the configuration wizard."""
        try:
            # Check if config already exists
            if self.config_path.exists():
                self._load_existing_config()
                self.menu_mode()
            else:
                self.wizard_mode()
        except KeyboardInterrupt:
            console.print("\n\n[yellow]Configuration cancelled.[/yellow]")
            sys.exit(0)

    def _load_existing_config(self):
        """Load existing configuration."""
        try:
            with open(self.config_path) as f:
                self.config_data = yaml.safe_load(f) or {}
        except Exception as e:
            console.print(f"[red]Error loading config:[/red] {e}")
            self.config_data = {}

    def wizard_mode(self):
        """Step-by-step wizard for first-time setup."""
        self._show_welcome()

        console.print("\n[bold cyan]Let's configure your services...[/bold cyan]\n")

        # Initialize empty config structure
        self.config_data = {
            "plex": {},
            "letterboxd": {"rss": [], "watchlist": [], "min_rating": 0},
            "sonarr": {"enabled": False},
            "radarr": {"enabled": False},
            "tmdb": {},
            "sync": {},
        }

        # Required: Plex
        console.print("[bold]Step 1/6: Plex Configuration[/bold] (Required)")
        self._configure_plex()

        # Sonarr
        console.print("\n[bold]Step 2/6: Sonarr Configuration[/bold] (Optional)")
        if Confirm.ask("Do you want to enable Sonarr for TV shows?", default=False):
            self._configure_sonarr()
        else:
            console.print("[dim]Skipping Sonarr configuration[/dim]")

        # Radarr
        console.print("\n[bold]Step 3/6: Radarr Configuration[/bold] (Optional)")
        if Confirm.ask("Do you want to enable Radarr for movies?", default=False):
            self._configure_radarr()
        else:
            console.print("[dim]Skipping Radarr configuration[/dim]")

        # Check at least one *arr service enabled
        if not self.config_data["sonarr"].get("enabled") and not self.config_data["radarr"].get("enabled"):
            console.print(
                "\n[red]Error:[/red] You must enable at least one of Sonarr or Radarr to use lumarr."
            )
            if Confirm.ask("Would you like to configure Radarr now?", default=True):
                self._configure_radarr()
            else:
                console.print("[yellow]Configuration incomplete. Exiting.[/yellow]")
                sys.exit(1)

        # Letterboxd
        console.print("\n[bold]Step 4/6: Letterboxd Configuration[/bold] (Optional)")
        if Confirm.ask("Do you want to sync from Letterboxd?", default=False):
            self._configure_letterboxd()
        else:
            console.print("[dim]Skipping Letterboxd configuration[/dim]")

        # TMDB
        console.print("\n[bold]Step 5/6: TMDB Configuration[/bold] (Optional but recommended)")
        if Confirm.ask("Do you want to configure TMDB API for better ID resolution?", default=True):
            self._configure_tmdb()
        else:
            console.print("[dim]Skipping TMDB configuration[/dim]")

        # Sync settings
        console.print("\n[bold]Step 6/6: Sync Settings[/bold]")
        self._configure_sync_settings()

        # Preview and save
        self._preview_and_save()

    def menu_mode(self):
        """Interactive menu for editing existing configuration."""
        while True:
            console.clear()
            self._render_menu()

            choice = Prompt.ask(
                "\nSelect a service to configure",
                choices=["1", "2", "3", "4", "5", "6", "t", "T", "s", "S", "q", "Q"],
            ).lower()

            if choice == "1":
                self._configure_plex()
                self.changes_made = True
            elif choice == "2":
                self._configure_letterboxd()
                self.changes_made = True
            elif choice == "3":
                self._configure_sonarr()
                self.changes_made = True
            elif choice == "4":
                self._configure_radarr()
                self.changes_made = True
            elif choice == "5":
                self._configure_tmdb()
                self.changes_made = True
            elif choice == "6":
                self._configure_sync_settings()
                self.changes_made = True
            elif choice == "t":
                self._test_all_connections()
            elif choice == "s":
                if self.changes_made:
                    self._save_config()
                    console.print("\n[green]✓[/green] Configuration saved successfully!")
                else:
                    console.print("\n[yellow]No changes to save.[/yellow]")
                break
            elif choice == "q":
                if self.changes_made:
                    if Confirm.ask("\n[yellow]You have unsaved changes. Quit anyway?[/yellow]", default=False):
                        console.print("[yellow]Configuration not saved.[/yellow]")
                        break
                else:
                    break

    def _show_welcome(self):
        """Show welcome screen for wizard mode."""
        welcome_text = """
[bold cyan]Welcome to Lumarr Configuration Wizard![/bold cyan]

This wizard will help you set up lumarr to sync your Plex watchlist
with Sonarr and Radarr. You can also configure Letterboxd integration.

[bold]What you'll configure:[/bold]
  • Plex authentication
  • Sonarr (for TV shows)
  • Radarr (for movies)
  • Letterboxd (optional)
  • TMDB API (optional, for better ID resolution)
  • Sync settings

Press Ctrl+C at any time to cancel.
        """
        console.print(Panel(welcome_text, border_style="cyan"))

    def _render_menu(self):
        """Render the main menu."""
        title = Panel("[bold cyan]Lumarr Configuration[/bold cyan]", border_style="cyan")
        console.print(title)

        # Services table
        services_table = Table(title="\nServices", show_header=False, box=None, padding=(0, 2))
        services_table.add_column("Number", style="cyan", width=5)
        services_table.add_column("Service", style="white", width=15)
        services_table.add_column("Status", style="white", width=15)
        services_table.add_column("Details", style="dim", width=30)

        # Add service rows
        services = [
            ("1", "Plex", self._get_service_status("plex"), self._get_service_detail("plex")),
            ("2", "Letterboxd", self._get_service_status("letterboxd"), self._get_service_detail("letterboxd")),
            ("3", "Sonarr", self._get_service_status("sonarr"), self._get_service_detail("sonarr")),
            ("4", "Radarr", self._get_service_status("radarr"), self._get_service_detail("radarr")),
            ("5", "TMDB", self._get_service_status("tmdb"), self._get_service_detail("tmdb")),
            ("6", "Sync Settings", "[green]✓ Configured[/green]", ""),
        ]

        for number, service, status, details in services:
            services_table.add_row(f"[{number}]", service, status, details)

        console.print(Panel(services_table, border_style="blue"))

        # Actions
        actions = Table(title="\nActions", show_header=False, box=None, padding=(0, 2))
        actions.add_column("Key", style="cyan", width=5)
        actions.add_column("Action", style="white")

        actions.add_row("[T]", "Test all connections")
        actions.add_row("[S]", "Save and exit")
        actions.add_row("[Q]", "Quit without saving")

        console.print(Panel(actions, border_style="green"))

    def _get_service_status(self, service: str) -> str:
        """Get service configuration status.

        Args:
            service: Service name

        Returns:
            Formatted status string
        """
        if service == "plex":
            return "[green]✓ Configured[/green]" if self.config_data.get("plex", {}).get("token") else "[red]✗ Not configured[/red]"
        elif service == "letterboxd":
            lbox = self.config_data.get("letterboxd", {})
            rss = lbox.get("rss", [])
            watchlist = lbox.get("watchlist", [])
            return "[green]✓ Configured[/green]" if (rss or watchlist) else "[red]✗ Not configured[/red]"
        elif service == "sonarr":
            sonarr = self.config_data.get("sonarr", {})
            if sonarr.get("enabled"):
                return "[green]✓ Enabled[/green]"
            else:
                return "[dim]✗ Disabled[/dim]"
        elif service == "radarr":
            radarr = self.config_data.get("radarr", {})
            if radarr.get("enabled"):
                return "[green]✓ Enabled[/green]"
            else:
                return "[dim]✗ Disabled[/dim]"
        elif service == "tmdb":
            return "[green]✓ Configured[/green]" if self.config_data.get("tmdb", {}).get("api_key") else "[yellow]⚠ Optional[/yellow]"

        return "[dim]Not configured[/dim]"

    def _get_service_detail(self, service: str) -> str:
        """Get service detail (URL or other info).

        Args:
            service: Service name

        Returns:
            Detail string
        """
        if service == "plex":
            return "Plex authentication"
        elif service == "letterboxd":
            lbox = self.config_data.get("letterboxd", {})
            rss = lbox.get("rss", [])
            watchlist = lbox.get("watchlist", [])
            users = []
            if rss:
                users.extend(rss)
            if watchlist:
                users.extend(watchlist)
            return ", ".join(users[:2]) + ("..." if len(users) > 2 else "") if users else ""
        elif service == "sonarr":
            url = self.config_data.get("sonarr", {}).get("url")
            return url if url else ""
        elif service == "radarr":
            url = self.config_data.get("radarr", {}).get("url")
            return url if url else ""
        elif service == "tmdb":
            return "ID resolution" if self.config_data.get("tmdb", {}).get("api_key") else ""

        return ""

    def _configure_plex(self):
        """Configure Plex service."""
        console.print("\n[bold cyan]Plex Configuration[/bold cyan]")
        console.print("[dim]Get your Plex token from: https://support.plex.tv/articles/204059436[/dim]\n")

        if "plex" not in self.config_data:
            self.config_data["plex"] = {}

        # Token
        current_token = self.config_data["plex"].get("token", "")
        token = Prompt.ask(
            "Plex Token",
            default=current_token if current_token else None,
        )
        self.config_data["plex"]["token"] = token.strip()

        # Client identifier
        current_client_id = self.config_data["plex"].get("client_identifier", "lumarr-sync")
        client_id = Prompt.ask(
            "Client Identifier",
            default=current_client_id,
        )
        self.config_data["plex"]["client_identifier"] = client_id.strip()

        # RSS ID (optional)
        current_rss_id = self.config_data["plex"].get("rss_id", "")
        if Confirm.ask("Do you want to use Plex RSS feed instead of API? (faster, optional)", default=False):
            console.print("[dim]Example RSS URL: https://rss.plex.tv/13215c36-af9c-4ff3-8414-cfdb395e70ee[/dim]")
            console.print("[dim]Enter just the UUID part: 13215c36-af9c-4ff3-8414-cfdb395e70ee[/dim]")
            rss_id = Prompt.ask("RSS Feed UUID", default=current_rss_id if current_rss_id else "")
            self.config_data["plex"]["rss_id"] = rss_id.strip() if rss_id.strip() else ""
        else:
            self.config_data["plex"]["rss_id"] = ""

        # Test connection
        if Confirm.ask("\nTest Plex connection now?", default=True):
            self._test_plex_connection()

    def _configure_letterboxd(self):
        """Configure Letterboxd service."""
        console.print("\n[bold cyan]Letterboxd Configuration[/bold cyan]")

        if "letterboxd" not in self.config_data:
            self.config_data["letterboxd"] = {"rss": [], "watchlist": [], "min_rating": 0}

        # RSS usernames
        if Confirm.ask("Do you want to sync watched movies from Letterboxd RSS feeds?", default=False):
            console.print("\n[dim]Enter Letterboxd usernames (one at a time, press Enter with empty input to finish)[/dim]")
            rss_users = []
            while True:
                username = Prompt.ask("Username", default="").strip()
                if not username:
                    break
                if self._validate_letterboxd_username(username):
                    rss_users.append(username)
                else:
                    console.print("[red]Invalid username. Use only letters, numbers, underscore, and hyphen.[/red]")
            self.config_data["letterboxd"]["rss"] = rss_users
        else:
            self.config_data["letterboxd"]["rss"] = []

        # Watchlist usernames
        if Confirm.ask("\nDo you want to scrape Letterboxd watchlists?", default=False):
            console.print("\n[dim]Enter Letterboxd usernames (one at a time, press Enter with empty input to finish)[/dim]")
            watchlist_users = []
            while True:
                username = Prompt.ask("Username", default="").strip()
                if not username:
                    break
                if self._validate_letterboxd_username(username):
                    watchlist_users.append(username)
                else:
                    console.print("[red]Invalid username. Use only letters, numbers, underscore, and hyphen.[/red]")
            self.config_data["letterboxd"]["watchlist"] = watchlist_users
        else:
            self.config_data["letterboxd"]["watchlist"] = []

        # Min rating
        if Confirm.ask("\nDo you want to filter movies by minimum rating?", default=False):
            while True:
                try:
                    rating = Prompt.ask("Minimum rating (0.0-5.0)", default="0")
                    rating_float = float(rating)
                    if 0 <= rating_float <= 5:
                        self.config_data["letterboxd"]["min_rating"] = rating_float
                        break
                    else:
                        console.print("[red]Rating must be between 0.0 and 5.0[/red]")
                except ValueError:
                    console.print("[red]Please enter a valid number[/red]")
        else:
            self.config_data["letterboxd"]["min_rating"] = 0

    def _configure_sonarr(self):
        """Configure Sonarr service."""
        console.print("\n[bold cyan]Sonarr Configuration[/bold cyan]")

        if "sonarr" not in self.config_data:
            self.config_data["sonarr"] = {}

        # Enable
        current_enabled = self.config_data["sonarr"].get("enabled", False)
        enabled = Confirm.ask("Enable Sonarr?", default=current_enabled)
        self.config_data["sonarr"]["enabled"] = enabled

        if not enabled:
            console.print("[dim]Sonarr disabled[/dim]")
            return

        # URL
        current_url = self.config_data["sonarr"].get("url", "http://localhost:8989")
        while True:
            url = Prompt.ask("Sonarr URL", default=current_url)
            valid, error = self._validate_url(url)
            if valid:
                self.config_data["sonarr"]["url"] = url.rstrip("/")
                break
            else:
                console.print(f"[red]{error}[/red]")

        # API Key
        current_api_key = self.config_data["sonarr"].get("api_key", "")
        api_key = Prompt.ask("Sonarr API Key", default=current_api_key if current_api_key else None)
        self.config_data["sonarr"]["api_key"] = api_key.strip()

        # Test and get profiles
        if Confirm.ask("\nTest Sonarr connection and fetch settings?", default=True):
            profiles, root_folders = self._test_sonarr_connection()
            if profiles and root_folders:
                self._select_sonarr_settings(profiles, root_folders)
            else:
                self._configure_sonarr_defaults()
        else:
            self._configure_sonarr_defaults()

    def _configure_sonarr_defaults(self):
        """Configure Sonarr with default values."""
        current_profile = self.config_data["sonarr"].get("quality_profile", 1)
        profile = IntPrompt.ask("Quality Profile ID", default=current_profile)
        self.config_data["sonarr"]["quality_profile"] = profile

        current_root = self.config_data["sonarr"].get("root_folder", "/tv")
        root_folder = Prompt.ask("Root Folder Path", default=current_root)
        self.config_data["sonarr"]["root_folder"] = root_folder

        current_series_type = self.config_data["sonarr"].get("series_type", "standard")
        series_type = Prompt.ask(
            "Series Type",
            choices=["standard", "daily", "anime"],
            default=current_series_type,
        )
        self.config_data["sonarr"]["series_type"] = series_type

        current_monitor_all = self.config_data["sonarr"].get("monitor_all", False)
        monitor_all = Confirm.ask("Monitor all seasons?", default=current_monitor_all)
        self.config_data["sonarr"]["monitor_all"] = monitor_all

        current_season_folder = self.config_data["sonarr"].get("season_folder", True)
        season_folder = Confirm.ask("Use season folders?", default=current_season_folder)
        self.config_data["sonarr"]["season_folder"] = season_folder

    def _configure_radarr(self):
        """Configure Radarr service."""
        console.print("\n[bold cyan]Radarr Configuration[/bold cyan]")

        if "radarr" not in self.config_data:
            self.config_data["radarr"] = {}

        # Enable
        current_enabled = self.config_data["radarr"].get("enabled", False)
        enabled = Confirm.ask("Enable Radarr?", default=current_enabled)
        self.config_data["radarr"]["enabled"] = enabled

        if not enabled:
            console.print("[dim]Radarr disabled[/dim]")
            return

        # URL
        current_url = self.config_data["radarr"].get("url", "http://localhost:7878")
        while True:
            url = Prompt.ask("Radarr URL", default=current_url)
            valid, error = self._validate_url(url)
            if valid:
                self.config_data["radarr"]["url"] = url.rstrip("/")
                break
            else:
                console.print(f"[red]{error}[/red]")

        # API Key
        current_api_key = self.config_data["radarr"].get("api_key", "")
        api_key = Prompt.ask("Radarr API Key", default=current_api_key if current_api_key else None)
        self.config_data["radarr"]["api_key"] = api_key.strip()

        # Test and get profiles
        if Confirm.ask("\nTest Radarr connection and fetch settings?", default=True):
            profiles, root_folders = self._test_radarr_connection()
            if profiles and root_folders:
                self._select_radarr_settings(profiles, root_folders)
            else:
                self._configure_radarr_defaults()
        else:
            self._configure_radarr_defaults()

    def _configure_radarr_defaults(self):
        """Configure Radarr with default values."""
        current_profile = self.config_data["radarr"].get("quality_profile", 1)
        profile = IntPrompt.ask("Quality Profile ID", default=current_profile)
        self.config_data["radarr"]["quality_profile"] = profile

        current_root = self.config_data["radarr"].get("root_folder", "/movies")
        root_folder = Prompt.ask("Root Folder Path", default=current_root)
        self.config_data["radarr"]["root_folder"] = root_folder

        current_monitored = self.config_data["radarr"].get("monitored", True)
        monitored = Confirm.ask("Monitor movies?", default=current_monitored)
        self.config_data["radarr"]["monitored"] = monitored

        current_search = self.config_data["radarr"].get("search_on_add", True)
        search_on_add = Confirm.ask("Search immediately when added?", default=current_search)
        self.config_data["radarr"]["search_on_add"] = search_on_add

    def _configure_tmdb(self):
        """Configure TMDB service."""
        console.print("\n[bold cyan]TMDB Configuration[/bold cyan]")
        console.print("[dim]Get your API key from: https://www.themoviedb.org/settings/api[/dim]\n")

        if "tmdb" not in self.config_data:
            self.config_data["tmdb"] = {}

        current_api_key = self.config_data["tmdb"].get("api_key", "")
        api_key = Prompt.ask("TMDB API Key (leave empty to skip)", default=current_api_key if current_api_key else "")
        self.config_data["tmdb"]["api_key"] = api_key.strip()

        if api_key.strip() and Confirm.ask("\nTest TMDB connection?", default=True):
            self._test_tmdb_connection()

    def _configure_sync_settings(self):
        """Configure sync settings."""
        console.print("\n[bold cyan]Sync Settings[/bold cyan]")

        if "sync" not in self.config_data:
            self.config_data["sync"] = {}

        # Database path
        current_db = self.config_data["sync"].get("database", "./lumarr.db")
        db_path = Prompt.ask("Database path", default=current_db)
        self.config_data["sync"]["database"] = db_path

        # Dry run
        current_dry_run = self.config_data["sync"].get("dry_run", False)
        dry_run = Confirm.ask("Enable dry-run mode by default?", default=current_dry_run)
        self.config_data["sync"]["dry_run"] = dry_run

        # Ignore existing
        current_ignore = self.config_data["sync"].get("ignore_existing", False)
        ignore_existing = Confirm.ask("Ignore existing watchlist items on first run?", default=current_ignore)
        self.config_data["sync"]["ignore_existing"] = ignore_existing

        # Cache max age
        current_cache = self.config_data["sync"].get("cache_max_age_days", 7)
        cache_days = IntPrompt.ask("Metadata cache max age (days)", default=current_cache)
        self.config_data["sync"]["cache_max_age_days"] = cache_days

        # Log level
        current_log_level = self.config_data["sync"].get("log_level", "INFO")
        log_level = Prompt.ask(
            "Log level",
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            default=current_log_level,
        )
        self.config_data["sync"]["log_level"] = log_level

        # Log file
        current_log_file = self.config_data["sync"].get("log_file", "")
        log_file = Prompt.ask("Log file path (leave empty for stdout only)", default=current_log_file)
        self.config_data["sync"]["log_file"] = log_file.strip()

    def _test_plex_connection(self):
        """Test Plex connection."""
        with console.status("[cyan]Testing Plex connection...[/cyan]", spinner="dots"):
            try:
                # Create temporary database for testing
                db = Database(":memory:")
                plex = PlexApi(
                    auth_token=self.config_data["plex"]["token"],
                    client_identifier=self.config_data["plex"]["client_identifier"],
                    database=db,
                    rss_id=self.config_data["plex"].get("rss_id"),
                )
                if plex.ping():
                    console.print("[green]✓[/green] Plex connection successful!")
                else:
                    console.print("[red]✗[/red] Failed to connect to Plex")
            except Exception as e:
                console.print(f"[red]✗[/red] Plex connection failed: {e}")

    def _test_sonarr_connection(self) -> Tuple[Optional[list], Optional[list]]:
        """Test Sonarr connection and fetch profiles.

        Returns:
            Tuple of (quality_profiles, root_folders) or (None, None) on error
        """
        with console.status("[cyan]Testing Sonarr connection...[/cyan]", spinner="dots"):
            try:
                sonarr = SonarrApi(
                    url=self.config_data["sonarr"]["url"],
                    api_key=self.config_data["sonarr"]["api_key"],
                    quality_profile=1,
                    root_folder="/",
                )

                if sonarr.test_connection():
                    console.print("[green]✓[/green] Sonarr connection successful!")

                    # Fetch profiles and folders
                    profiles = sonarr.get_quality_profiles()
                    folders = sonarr.get_root_folders()

                    return profiles, folders
                else:
                    console.print("[red]✗[/red] Failed to connect to Sonarr")
                    return None, None
            except Exception as e:
                console.print(f"[red]✗[/red] Sonarr connection failed: {e}")
                return None, None

    def _test_radarr_connection(self) -> Tuple[Optional[list], Optional[list]]:
        """Test Radarr connection and fetch profiles.

        Returns:
            Tuple of (quality_profiles, root_folders) or (None, None) on error
        """
        with console.status("[cyan]Testing Radarr connection...[/cyan]", spinner="dots"):
            try:
                radarr = RadarrApi(
                    url=self.config_data["radarr"]["url"],
                    api_key=self.config_data["radarr"]["api_key"],
                    quality_profile=1,
                    root_folder="/",
                )

                if radarr.test_connection():
                    console.print("[green]✓[/green] Radarr connection successful!")

                    # Fetch profiles and folders
                    profiles = radarr.get_quality_profiles()
                    folders = radarr.get_root_folders()

                    return profiles, folders
                else:
                    console.print("[red]✗[/red] Failed to connect to Radarr")
                    return None, None
            except Exception as e:
                console.print(f"[red]✗[/red] Radarr connection failed: {e}")
                return None, None

    def _test_tmdb_connection(self):
        """Test TMDB connection."""
        with console.status("[cyan]Testing TMDB connection...[/cyan]", spinner="dots"):
            try:
                tmdb = TmdbApi(api_key=self.config_data["tmdb"]["api_key"])
                if tmdb.is_configured():
                    # Try a simple search to verify the key works
                    console.print("[green]✓[/green] TMDB connection successful!")
                else:
                    console.print("[red]✗[/red] TMDB API key not configured correctly")
            except Exception as e:
                console.print(f"[red]✗[/red] TMDB connection failed: {e}")

    def _select_sonarr_settings(self, profiles: list, root_folders: list):
        """Let user select Sonarr quality profile and root folder.

        Args:
            profiles: List of quality profiles
            root_folders: List of root folders
        """
        console.print("\n[bold]Available Quality Profiles:[/bold]")
        for i, profile in enumerate(profiles, 1):
            console.print(f"  [{i}] {profile['name']} (ID: {profile['id']})")

        while True:
            choice = IntPrompt.ask("Select quality profile", default=1)
            if 1 <= choice <= len(profiles):
                self.config_data["sonarr"]["quality_profile"] = profiles[choice - 1]["id"]
                break
            else:
                console.print(f"[red]Please select a number between 1 and {len(profiles)}[/red]")

        console.print("\n[bold]Available Root Folders:[/bold]")
        for i, folder in enumerate(root_folders, 1):
            free_space_gb = folder.get("freeSpace", 0) / (1024**3)
            console.print(f"  [{i}] {folder['path']} ({free_space_gb:.1f} GB free)")

        while True:
            choice = IntPrompt.ask("Select root folder", default=1)
            if 1 <= choice <= len(root_folders):
                self.config_data["sonarr"]["root_folder"] = root_folders[choice - 1]["path"]
                break
            else:
                console.print(f"[red]Please select a number between 1 and {len(root_folders)}[/red]")

        # Other settings with defaults
        current_series_type = self.config_data["sonarr"].get("series_type", "standard")
        series_type = Prompt.ask(
            "\nSeries Type",
            choices=["standard", "daily", "anime"],
            default=current_series_type,
        )
        self.config_data["sonarr"]["series_type"] = series_type

        current_monitor_all = self.config_data["sonarr"].get("monitor_all", False)
        monitor_all = Confirm.ask("Monitor all seasons?", default=current_monitor_all)
        self.config_data["sonarr"]["monitor_all"] = monitor_all

        current_season_folder = self.config_data["sonarr"].get("season_folder", True)
        season_folder = Confirm.ask("Use season folders?", default=current_season_folder)
        self.config_data["sonarr"]["season_folder"] = season_folder

    def _select_radarr_settings(self, profiles: list, root_folders: list):
        """Let user select Radarr quality profile and root folder.

        Args:
            profiles: List of quality profiles
            root_folders: List of root folders
        """
        console.print("\n[bold]Available Quality Profiles:[/bold]")
        for i, profile in enumerate(profiles, 1):
            console.print(f"  [{i}] {profile['name']} (ID: {profile['id']})")

        while True:
            choice = IntPrompt.ask("Select quality profile", default=1)
            if 1 <= choice <= len(profiles):
                self.config_data["radarr"]["quality_profile"] = profiles[choice - 1]["id"]
                break
            else:
                console.print(f"[red]Please select a number between 1 and {len(profiles)}[/red]")

        console.print("\n[bold]Available Root Folders:[/bold]")
        for i, folder in enumerate(root_folders, 1):
            free_space_gb = folder.get("freeSpace", 0) / (1024**3)
            console.print(f"  [{i}] {folder['path']} ({free_space_gb:.1f} GB free)")

        while True:
            choice = IntPrompt.ask("Select root folder", default=1)
            if 1 <= choice <= len(root_folders):
                self.config_data["radarr"]["root_folder"] = root_folders[choice - 1]["path"]
                break
            else:
                console.print(f"[red]Please select a number between 1 and {len(root_folders)}[/red]")

        # Other settings
        current_monitored = self.config_data["radarr"].get("monitored", True)
        monitored = Confirm.ask("\nMonitor movies?", default=current_monitored)
        self.config_data["radarr"]["monitored"] = monitored

        current_search = self.config_data["radarr"].get("search_on_add", True)
        search_on_add = Confirm.ask("Search immediately when added?", default=current_search)
        self.config_data["radarr"]["search_on_add"] = search_on_add

    def _test_all_connections(self):
        """Test all configured service connections."""
        console.print("\n[bold cyan]Testing all connections...[/bold cyan]\n")

        # Plex
        if self.config_data.get("plex", {}).get("token"):
            self._test_plex_connection()
        else:
            console.print("[yellow]⚠[/yellow] Plex not configured")

        # Sonarr
        if self.config_data.get("sonarr", {}).get("enabled"):
            self._test_sonarr_connection()
        else:
            console.print("[dim]Sonarr disabled[/dim]")

        # Radarr
        if self.config_data.get("radarr", {}).get("enabled"):
            self._test_radarr_connection()
        else:
            console.print("[dim]Radarr disabled[/dim]")

        # TMDB
        if self.config_data.get("tmdb", {}).get("api_key"):
            self._test_tmdb_connection()
        else:
            console.print("[yellow]⚠[/yellow] TMDB not configured (optional)")

        console.print("\n[green]Testing complete![/green]")
        Prompt.ask("\nPress Enter to continue")

    def _preview_and_save(self):
        """Preview configuration and save."""
        console.print("\n[bold cyan]Configuration Preview[/bold cyan]\n")

        # Convert to YAML and display
        yaml_str = yaml.dump(self.config_data, default_flow_style=False, sort_keys=False)
        syntax = Syntax(yaml_str, "yaml", theme="monokai", line_numbers=False)
        console.print(Panel(syntax, border_style="green"))

        if Confirm.ask("\nSave this configuration?", default=True):
            self._save_config()
            console.print(f"\n[green]✓[/green] Configuration saved to {self.config_path}")
            console.print("\n[bold]You can now run:[/bold] lumarr sync")
        else:
            console.print("[yellow]Configuration not saved.[/yellow]")

    def _save_config(self):
        """Save configuration to file."""
        try:
            # Create backup if file exists
            if self.config_path.exists():
                backup_path = self.config_path.with_suffix(".yaml.backup")
                self.config_path.rename(backup_path)
                console.print(f"[dim]Backup saved to {backup_path}[/dim]")

            # Write new config
            with open(self.config_path, "w") as f:
                yaml.dump(self.config_data, f, default_flow_style=False, sort_keys=False)

            self.changes_made = False
        except Exception as e:
            console.print(f"[red]Error saving configuration:[/red] {e}")
            sys.exit(1)

    @staticmethod
    def _validate_url(url: str) -> Tuple[bool, str]:
        """Validate URL format.

        Args:
            url: URL to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not url:
            return False, "URL cannot be empty"

        if not url.startswith(("http://", "https://")):
            return False, "URL must start with http:// or https://"

        # Basic URL pattern check
        url_pattern = re.compile(
            r"^https?://"  # http:// or https://
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
            r"localhost|"  # localhost...
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
            r"(?::\d+)?"  # optional port
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )

        if not url_pattern.match(url):
            return False, "Invalid URL format"

        return True, ""

    @staticmethod
    def _validate_letterboxd_username(username: str) -> bool:
        """Validate Letterboxd username format.

        Args:
            username: Username to validate

        Returns:
            True if valid, False otherwise
        """
        if not username:
            return False

        # Only letters, numbers, underscore, hyphen
        pattern = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")
        return bool(pattern.match(username))
