# Lumarr

A lightweight CLI tool to automatically sync your Plex watchlist and Letterboxd lists with Sonarr and Radarr.

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![PyPI version](https://img.shields.io/pypi/v/lumarr.svg)](https://pypi.org/project/lumarr/)
[![Docker Hub](https://img.shields.io/docker/v/blueconfetti/lumarr?label=docker)](https://hub.docker.com/r/blueconfetti/lumarr)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## Overview

Lumarr monitors your Plex watchlist and Letterboxd activity, automatically adding movies and TV shows to your Sonarr and Radarr instances. It runs as a lightweight CLI tool with support for one-time syncs, scheduled runs, or continuous monitoring.

### Key Features

- **Plex Watchlist Sync** - Automatically add watchlist items to Sonarr/Radarr
- **Letterboxd Integration** - Sync watched movies and watchlists from Letterboxd
- **Smart Duplicate Prevention** - Local database tracks synced items
- **Multiple Sync Modes** - One-time, scheduled, or continuous monitoring
- **Interactive Configuration** - Easy setup wizard for first-time configuration
- **Modular CLI Toolkit** - Commands for status checks, history browsing, listing, and service discovery
- **Event Hooks** - Trigger shell commands or webhooks on sync completion or errors
- **Docker Support** - Run in a container for easy deployment

## Quick Start

### Installation

**Using pip (Recommended):**

```bash
pip install lumarr
```

**Using Docker:**

```bash
docker pull blueconfetti/lumarr:latest
```

**From Source:**

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone https://github.com/yourusername/lumarr.git
cd lumarr
uv pip install -e .
```

See [Installation Guide](docs/installation.md) for more installation options.

### Configuration

1. **Create config file:**
   ```bash
   cp config.example.yaml config.yaml
   ```

2. **Run interactive wizard:**
   ```bash
   lumarr config
   ```

3. **Or manually edit** `config.yaml` with your API keys and settings

See [Configuration Guide](docs/configuration.md) for detailed configuration options.

### Usage

```bash
# Test connections
lumarr status

# Inspect current watchlist and Letterboxd inputs
lumarr list
lumarr list letterboxd --detailed

# Preview sync (dry run)
lumarr sync --dry-run

# Sync once or monitor continuously
lumarr sync
lumarr sync --follow

# Review sync history or clear it when needed
lumarr history
lumarr clear

# Discover service configuration details
lumarr sonarr info
lumarr radarr info
```

See [CLI Reference](docs/cli-reference.md) for all available commands.

## How It Works

1. Connects to Plex (via API or RSS feed) to fetch your watchlist
2. Optionally fetches Letterboxd watched movies and watchlists
3. Extracts TMDB, TVDB, and IMDB IDs from metadata
4. Checks local database to skip already-synced items
5. Adds new movies to Radarr and TV shows to Sonarr
6. Records sync history to prevent duplicates

**Performance:**
- RSS Feed mode: 1 HTTP request for entire watchlist
- API mode with caching: ~1-2 requests per sync
- Follow mode: Continuous monitoring with configurable intervals

## Documentation

- [Installation Guide](docs/installation.md) - Detailed installation instructions
- [Configuration Guide](docs/configuration.md) - Complete configuration reference
- [CLI Reference](docs/cli-reference.md) - All commands and options
- [Docker Guide](docs/docker.md) - Running with Docker/Docker Compose

## Requirements

- Python 3.9 or higher
- Plex account with authentication token
- Sonarr and/or Radarr instance
- Optional: TMDB API key for enhanced ID resolution
- Optional: Letterboxd account for Letterboxd sync

## Deployment Options

### Docker (Recommended for Production)

```bash
cd docker
docker-compose up -d
```

See [Docker Guide](docs/docker.md) for details.

### Systemd Service

```ini
[Unit]
Description=Lumarr Sync Service
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/lumarr
ExecStart=/usr/bin/lumarr sync --follow
Restart=always

[Install]
WantedBy=multi-user.target
```

### Cron

```bash
# Every 6 hours
0 */6 * * * cd /path/to/lumarr && lumarr sync
```

## Architecture

```
lumarr/
├── src/lumarr/
│   ├── api/                 # API clients (Plex, Sonarr, Radarr, TMDB, Letterboxd)
│   ├── cli/                 # Modular Click-based CLI implementation
│   │   ├── __init__.py      # CLI entrypoint and shared options
│   │   ├── commands/        # Command implementations (sync, list, status, etc.)
│   │   ├── groups/          # Command groups for Radarr/Sonarr helpers
│   │   ├── core/            # Context handling, decorators, hooks, plugin loader
│   │   ├── display/         # Rich console helpers and table formatters
│   │   └── logic/           # CLI workflows (follow mode, baseline, sync helpers)
│   ├── config.py            # Configuration management
│   ├── db.py                # SQLite database operations
│   ├── models.py            # Data models
│   └── sync.py              # Sync orchestration
├── docker/                  # Docker configuration
├── docs/                    # Documentation
├── config.yaml              # Your configuration
└── lumarr.db               # SQLite database (auto-created)
```

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

This project was inspired by [Ombi](https://github.com/Ombi-app/Ombi)'s watchlist import feature, designed as a lightweight CLI alternative for users who only need watchlist syncing.

## Support

- [Documentation](docs/)
- [PyPI Package](https://pypi.org/project/lumarr/)
- [Docker Hub](https://hub.docker.com/r/blueconfetti/lumarr)
- [Configuration Examples](config.example.yaml)
