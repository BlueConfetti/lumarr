"""Letterboxd service and resolution helpers."""

import builtins

from ..display.console import console


class LetterboxdResolver:
    """Helper class for resolving Letterboxd usernames from config."""

    def __init__(self, config):
        """
        Initialize resolver with config.

        Args:
            config: Config object
        """
        self.config = config

    def resolve_rss_usernames(self, rss_overrides=()):
        """
        Determine Letterboxd RSS usernames from CLI overrides or config.

        Args:
            rss_overrides: Tuple of usernames provided via CLI

        Returns:
            List of usernames to fetch RSS feeds for
        """
        # CLI overrides take precedence
        usernames = [*rss_overrides]
        if usernames:
            return usernames

        # Try config.letterboxd.rss
        config_rss = self.config.get("letterboxd.rss")
        if config_rss:
            if isinstance(config_rss, str):
                return [config_rss]
            if isinstance(config_rss, builtins.list):
                return config_rss
            try:
                return builtins.list(config_rss)
            except TypeError:
                pass

        # Check for legacy config.letterboxd.usernames
        legacy_usernames = self.config.get("letterboxd.usernames")
        if legacy_usernames:
            console.print(
                "[yellow]Warning:[/yellow] 'letterboxd.usernames' is deprecated. "
                "Rename it to 'letterboxd.rss' in config.yaml."
            )
            if isinstance(legacy_usernames, str):
                return [legacy_usernames]
            if isinstance(legacy_usernames, builtins.list):
                return legacy_usernames
            try:
                return builtins.list(legacy_usernames)
            except TypeError:
                pass

        return []

    def resolve_watchlist_usernames(self, watchlist_overrides=()):
        """
        Determine Letterboxd watchlist usernames from CLI overrides or config.

        Args:
            watchlist_overrides: Tuple of usernames provided via CLI

        Returns:
            List of usernames to fetch watchlists for
        """
        # CLI overrides take precedence
        usernames = [*watchlist_overrides]
        if usernames:
            return usernames

        # Try config.letterboxd.watchlist
        config_watchlist = self.config.get("letterboxd.watchlist", [])
        if isinstance(config_watchlist, str):
            return [config_watchlist]
        if isinstance(config_watchlist, builtins.list):
            return config_watchlist
        try:
            return builtins.list(config_watchlist)
        except TypeError:
            return []

        return []

    def has_letterboxd_configured(self):
        """Check if any Letterboxd sources are configured."""
        rss_names = self.resolve_rss_usernames()
        watchlist_names = self.resolve_watchlist_usernames()
        return bool(rss_names or watchlist_names)
