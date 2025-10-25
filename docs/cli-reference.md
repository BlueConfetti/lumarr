# CLI Reference

Complete reference for all Lumarr commands and options.

## Global Options

Available for all commands:

- `--config`, `-c`: Path to config file (default: `config.yaml`)
- `--version`: Show version
- `--help`: Show help message

## Commands

### lumarr config

Launch the interactive configuration wizard to set up or modify your Lumarr configuration.

```bash
lumarr config
```

The wizard will guide you through configuring Plex, Sonarr, Radarr, Letterboxd, and other services.

### lumarr sync

Sync Plex watchlist and Letterboxd items to Sonarr and Radarr. Letterboxd items are automatically synced if configured in `config.yaml`.

**Basic usage:**

```bash
# Sync once
lumarr sync

# Dry run (preview without making changes)
lumarr sync --dry-run

# Follow mode (continuously monitor)
lumarr sync --follow
lumarr sync -f
```

**Options:**

- `--dry-run`: Preview changes without making them
- `--force-refresh`: Force refresh metadata cache
- `--follow`, `-f`: Continuously monitor watchlist (checks Plex every 5s, Letterboxd every 30s by default)
- `--ignore-existing`: Mark all current watchlist items as already synced (baseline mode)
- `--min-rating FLOAT`: Only sync Letterboxd movies with this rating or higher (0.0-5.0)

**Follow mode details:**

Follow mode is perfect for real-time syncing. It will:
- Check your watchlist at configured intervals (see `plex.sync_interval` and `letterboxd.sync_interval` in config)
- Use cached metadata for fast performance
- Add new items automatically as they appear
- Run until you press Ctrl+C
- Gracefully shutdown after the current sync completes

### lumarr status

Check connection status and show watchlist info.

```bash
lumarr status
```

Displays:
- Plex connection status and watchlist item count
- Sonarr connection status (if enabled)
- Radarr connection status (if enabled)
- Database statistics

### lumarr list

Display all items in your Plex watchlist with detailed information.

```bash
# Show table view with basic info
lumarr list

# Show detailed view with summaries and all metadata
lumarr list --detailed
```

**Options:**

- `--detailed`, `-d`: Show detailed view with summaries and all metadata
- `--force-refresh`: Force refresh metadata cache

**Displayed information:**
- Title, type (movie/show), year
- Content rating (PG, R, TV-MA, etc.)
- Genres
- Provider IDs (TMDB, TVDB, IMDB)
- Summary/description (in detailed mode)
- Studio information (in detailed mode)

### lumarr history

View recent sync history.

```bash
# Show last 100 records
lumarr history

# Show more records
lumarr history --limit 50
lumarr history -n 50
```

**Options:**

- `--limit`, `-n`: Number of recent records to show (default: 100)

### lumarr clear

Clear sync history database. Requires confirmation.

```bash
lumarr clear
```

**Warning:** This will remove all sync history from the database. Items will be synced again on the next run unless already present in Sonarr/Radarr.

### lumarr sonarr info

Show Sonarr configuration information (quality profiles, root folders, tags).

```bash
# Using config from config.yaml
lumarr sonarr info

# Override with command-line arguments
lumarr sonarr info --url http://localhost:8989 --api-key YOUR_API_KEY
```

**Options:**

- `--url`: Sonarr URL (overrides config)
- `--api-key`: Sonarr API key (overrides config)

**Displays:**
- Quality Profile IDs and names (for `quality_profile` setting)
- Root Folder paths and available space (for `root_folder` setting)
- Available tags

### lumarr radarr info

Show Radarr configuration information (quality profiles, root folders, tags).

```bash
# Using config from config.yaml
lumarr radarr info

# Override with command-line arguments
lumarr radarr info --url http://localhost:7878 --api-key YOUR_API_KEY
```

**Options:**

- `--url`: Radarr URL (overrides config)
- `--api-key`: Radarr API key (overrides config)

**Displays:**
- Quality Profile IDs and names (for `quality_profile` setting)
- Root Folder paths and available space (for `root_folder` setting)
- Available tags

### lumarr lbox list

List watched movies from Letterboxd. This command is for viewing items only; syncing is done via `lumarr sync`.

```bash
# Using usernames from config.yaml
lumarr lbox list

# Override with command-line arguments
lumarr lbox list --rss username1 --rss username2

# Scrape watchlists instead of RSS
lumarr lbox list --watchlist username1 --watchlist username2

# Require minimum star rating
lumarr lbox list --min-rating 4

# Show detailed view with ratings
lumarr lbox list --detailed
```

**Options:**

- `--rss`, `-r`: Letterboxd username(s) for RSS feeds (can specify multiple times, overrides config)
- `--watchlist`, `-w`: Letterboxd username(s) whose watchlists should be scraped (can specify multiple times, overrides config)
- `--min-rating`: Only include movies with this rating or higher (0.0-5.0)
- `--detailed`, `-d`: Show detailed view with ratings and summaries

**How it works:**
- Fetches RSS feeds from Letterboxd for watched entries
- Scrapes watchlist pages (all pages) for configured usernames
- Extracts movie title, year, rating (if available), and uses provided IDs (TMDB when present)
- **Note:** Watchlist items do not include ratings, so `--min-rating` filters only apply to RSS-sourced entries

## Examples

**Basic sync workflow:**

```bash
# First, check your connections
lumarr status

# Preview what would be synced
lumarr sync --dry-run

# Perform the actual sync
lumarr sync

# Check sync history
lumarr history
```

**Running in follow mode:**

```bash
# Continuously monitor Plex watchlist and Letterboxd
lumarr sync --follow

# Monitor with custom intervals (configure in config.yaml):
# plex.sync_interval: 10  # Check Plex every 10 seconds
# letterboxd.sync_interval: 60  # Check Letterboxd every minute
```

**Setting up ignore_existing mode:**

```bash
# First run: establish baseline (mark all current items as synced)
lumarr sync --ignore-existing

# Future runs: only sync new additions
lumarr sync
```

**Filtering Letterboxd by rating:**

```bash
# Only sync movies rated 4 stars or higher
lumarr sync --min-rating 4

# List Letterboxd movies rated 3.5 or higher
lumarr lbox list --min-rating 3.5 --detailed
```

**Discovering Sonarr/Radarr settings:**

```bash
# Get quality profiles and root folders for Sonarr
lumarr sonarr info

# Get quality profiles and root folders for Radarr
lumarr radarr info

# Use different credentials than config.yaml
lumarr radarr info --url http://192.168.1.100:7878 --api-key abc123
```

## Scheduling & Automation

### Option 1: Follow Mode (Recommended)

Run Lumarr in follow mode for real-time monitoring:

```bash
lumarr sync --follow
```

This continuously checks your watchlist at configured intervals and is perfect for running as a long-lived service. You can run it in a screen/tmux session, or set it up as a systemd service:

```ini
# /etc/systemd/system/lumarr.service
[Unit]
Description=Lumarr Sync Service
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/lumarr
ExecStart=/usr/bin/lumarr sync --follow
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Option 2: Scheduled Runs (Cron)

For periodic syncing instead of continuous monitoring, use cron:

```bash
# Run every 6 hours
0 */6 * * * cd /path/to/lumarr && /path/to/python -m lumarr.cli sync

# Run daily at 2 AM
0 2 * * * cd /path/to/lumarr && /path/to/python -m lumarr.cli sync
```

Or use systemd timers, launchd, or your preferred scheduler.

## Troubleshooting

### Plex Connection Failed

- Verify your Plex token is correct
- Ensure you have an active Plex Pass subscription (required for watchlist access)
- Check network connectivity to Plex servers

### Sonarr/Radarr Connection Failed

- Verify the URL is correct (include `http://` or `https://`)
- Check that the API key is valid
- Ensure Sonarr/Radarr is running and accessible

### "No TMDB/TVDB ID found"

- Some Plex items may not have the required IDs
- Configure TMDB API key for better ID resolution
- Manually add items to Sonarr/Radarr if automatic sync fails

### Items Added Multiple Times

- This shouldn't happen due to duplicate prevention
- If it does, check database integrity
- Use `lumarr clear` to reset sync history
