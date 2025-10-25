"""Configuration management."""

import logging
import sys
from pathlib import Path
from typing import Optional

import yaml


class ConfigError(Exception):
    """Configuration error."""
    pass


class Config:
    """Configuration container."""

    def __init__(self, config_path: str):
        """Load configuration from YAML file.

        Args:
            config_path: Path to config.yaml

        Raises:
            ConfigError: If config is invalid
        """
        self.config_path = Path(config_path)

        if not self.config_path.exists():
            raise ConfigError(
                f"Config file not found: {config_path}\n"
                "Copy config.example.yaml to config.yaml and fill in your settings."
            )

        try:
            with open(self.config_path) as f:
                self.data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in config file: {e}")

        self._validate()

    def _validate(self):
        """Validate required configuration."""
        if not self.data.get("plex", {}).get("token"):
            raise ConfigError("plex.token is required in config")

        has_sonarr = self.data.get("sonarr", {}).get("enabled", False)
        has_radarr = self.data.get("radarr", {}).get("enabled", False)

        if not has_sonarr and not has_radarr:
            raise ConfigError(
                "At least one of sonarr or radarr must be enabled"
            )

        if has_sonarr:
            if not self.data.get("sonarr", {}).get("url"):
                raise ConfigError("sonarr.url is required when sonarr is enabled")
            if not self.data.get("sonarr", {}).get("api_key"):
                raise ConfigError("sonarr.api_key is required when sonarr is enabled")

        if has_radarr:
            if not self.data.get("radarr", {}).get("url"):
                raise ConfigError("radarr.url is required when radarr is enabled")
            if not self.data.get("radarr", {}).get("api_key"):
                raise ConfigError("radarr.api_key is required when radarr is enabled")

    def get(self, key: str, default=None):
        """Get config value by dot-notation key.

        Args:
            key: Dot-notation key (e.g., 'plex.token')
            default: Default value if not found

        Returns:
            Config value or default
        """
        keys = key.split(".")
        value = self.data

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default

            if value is None:
                return default

        return value


def setup_logging(config: Config):
    """Setup logging configuration.

    Args:
        config: Config object
    """
    log_level_str = config.get("sync.log_level", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    log_file = config.get("sync.log_file")

    handlers = []

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)
    handlers.append(console_handler)

    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)

    logging.basicConfig(
        level=log_level,
        handlers=handlers,
    )

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
