# Lumarr Documentation

Complete documentation for Lumarr - a lightweight CLI tool to sync Plex watchlists and Letterboxd lists with Sonarr and Radarr.

## Getting Started

New to Lumarr? Start here:

1. [Installation Guide](installation.md) - Install Lumarr using uv, pip, or Docker
2. [Configuration Guide](configuration.md) - Set up your configuration file
3. [CLI Reference](cli-reference.md) - Learn the available commands

## Documentation Index

### [Installation Guide](installation.md)
Detailed installation instructions for multiple platforms and methods:
- Using uv (recommended)
- Using pip
- Using Docker
- From source
- Platform-specific notes

### [Configuration Guide](configuration.md)
Complete configuration reference covering:
- Plex configuration (API and RSS modes)
- Sonarr configuration
- Radarr configuration
- TMDB configuration
- Letterboxd configuration
- Sync settings and options
- Database schema
- Performance optimization

### [CLI Reference](cli-reference.md)
Command-line interface reference with examples:
- All available commands
- Command options and flags
- Usage examples
- Scheduling and automation
- Troubleshooting

### [Docker Guide](docker.md)
Running Lumarr in Docker containers:
- Docker Compose setup
- Docker run commands
- Volume configuration
- Environment variables
- Deployment strategies
- Networking
- Security best practices

## Quick Links

### Common Tasks

- [First time setup](installation.md#quick-start)
- [Configure Plex](configuration.md#plex-configuration)
- [Configure Letterboxd](configuration.md#letterboxd-configuration)
- [Run in Docker](docker.md#quick-start)
- [Set up continuous monitoring](cli-reference.md#lumarr-sync)
- [Troubleshoot connection issues](cli-reference.md#troubleshooting)

### Advanced Topics

- [RSS vs API mode for Plex](configuration.md#rss-feed-alternative-recommended)
- [Follow mode for continuous monitoring](cli-reference.md#lumarr-sync)
- [Ignore existing watchlist items](configuration.md#ignore_existing-option)
- [Filter Letterboxd by rating](cli-reference.md#filtering-letterboxd-by-rating)
- [Docker deployment strategies](docker.md#deployment-strategies)
- [Systemd service setup](cli-reference.md#option-1-follow-mode-recommended)

## Architecture

Lumarr is organized into several modules:

```
src/lumarr/
├── api/                 # API clients
│   ├── plex.py         # Plex API/RSS client
│   ├── sonarr.py       # Sonarr API client
│   ├── radarr.py       # Radarr API client
│   ├── tmdb.py         # TMDB API client
│   └── letterboxd.py   # Letterboxd scraper
├── cli.py              # Click-based CLI interface
├── config.py           # Configuration management
├── config_wizard.py    # Interactive setup wizard
├── db.py               # SQLite database operations
├── models.py           # Data models and enums
└── sync.py             # Sync orchestration logic
```

## Support

- [GitHub Issues](https://github.com/yourusername/lumarr/issues)
- [Main README](../README.md)
- [Configuration Examples](../config.example.yaml)

## Contributing

See the main [README](../README.md#contributing) for contribution guidelines.
