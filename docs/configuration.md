# Configuration Guide

This guide covers all configuration options for Lumarr. Configuration is stored in `config.yaml` in the project root.

## Quick Start

Copy the example configuration:

```bash
cp config.example.yaml config.yaml
```

Then edit `config.yaml` with your settings, or use the interactive wizard:

```bash
lumarr config
```

## Configuration Sections

### Plex Configuration

Get your Plex token from: https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/

```yaml
plex:
  token: "YOUR_PLEX_TOKEN"
  client_identifier: "lumarr-sync"
  rss_id: ""  # Optional: Use RSS feed instead of API (see below)
  sync_interval: 5  # Seconds between checks in follow mode (default: 5)
```

#### RSS Feed Alternative (Recommended)

Instead of using the Plex API (which requires multiple requests per item), you can use your watchlist RSS feed for much faster performance and to avoid rate limits.

**How to get your RSS feed ID:**

1. Log into Plex web app
2. Go to your Watchlist
3. Look for an RSS icon or "Subscribe" button
4. Copy the RSS feed URL (e.g., `https://rss.plex.tv/13215c36-af9c-4ff3-8414-cfdb395e70ee`)
5. Extract just the UUID part: `13215c36-af9c-4ff3-8414-cfdb395e70ee`
6. Add it to your config:

```yaml
plex:
  token: "YOUR_PLEX_TOKEN"
  client_identifier: "lumarr-sync"
  rss_id: "13215c36-af9c-4ff3-8414-cfdb395e70ee"
```

**Benefits of RSS:**
- Single HTTP request (vs 51 requests for 50 items with API)
- Faster response time
- No rate limiting concerns
- Provider IDs (TMDB, TVDB, IMDB) included directly in feed

### Sonarr Configuration

```yaml
sonarr:
  enabled: true
  url: "http://localhost:8989"
  api_key: "YOUR_SONARR_API_KEY"
  quality_profile: 1
  root_folder: "/tv"
  monitor_all: false        # false = latest season only, true = all seasons
  series_type: "standard"   # standard, daily, or anime
  season_folder: true
```

**Finding your settings:**

Use `lumarr sonarr info` to discover available quality profiles, root folders, and tags from your Sonarr instance.

### Radarr Configuration

```yaml
radarr:
  enabled: true
  url: "http://localhost:7878"
  api_key: "YOUR_RADARR_API_KEY"
  quality_profile: 1
  root_folder: "/movies"
  monitored: true
  search_on_add: true
```

**Finding your settings:**

Use `lumarr radarr info` to discover available quality profiles, root folders, and tags from your Radarr instance.

### TMDB Configuration (Optional but Recommended)

TMDB API helps resolve missing IDs. Get your API key from: https://www.themoviedb.org/settings/api

```yaml
tmdb:
  api_key: "YOUR_TMDB_API_KEY"
```

### Letterboxd Configuration (Optional)

Sync watched movies and watchlists from Letterboxd to Radarr:

```yaml
letterboxd:
  rss:
    - "your_username"
    - "another_username"
  watchlist:
    - "your_username"
    - "another_username"
  min_rating: 0  # Only sync movies rated this or higher (0.0-5.0)
  sync_interval: 30  # Seconds between checks in follow mode (default: 30)
```

**How to find your Letterboxd username:**
- Your username is in your profile URL: `https://letterboxd.com/username/`
- The RSS feed is automatically constructed: `https://letterboxd.com/username/rss/`
- The watchlist is available at `https://letterboxd.com/username/watchlist/` (all pages are scraped)
  - Each page is fetched once; `data-film-id` from `LazyPoster` entries is reused as the TMDB identifier
  - Watchlist items do not include ratings, so `--min-rating` filters apply only to RSS-sourced entries

**Note:** Letterboxd items are automatically synced when you run `lumarr sync` if configured. The `lbox list` command is for viewing items only.

### Sync Settings

```yaml
sync:
  database: "./lumarr.db"
  dry_run: false
  ignore_existing: false
  cache_max_age_days: 7
  log_level: "INFO"
  log_file: ""
```

#### ignore_existing Option

By default, lumarr will sync all items in your watchlist. If you want to only sync **new additions** to your watchlist (ignoring items that were already there), enable the `ignore_existing` option:

```yaml
sync:
  ignore_existing: true
```

**How it works:**
- On first run with `ignore_existing: true`, all current watchlist items are marked as "baseline"
- On subsequent runs, only items added to your watchlist **after** the first run will be synced
- Baseline items will be skipped

This is useful if you already have a large watchlist and only want to automatically sync new additions going forward.

## Database

Lumarr uses SQLite to track synced items and prevent duplicates. The database is created automatically at the path specified in your config (default: `./lumarr.db`).

### Schema

- **synced_items**: Tracks all sync operations
  - `rating_key`: Plex rating key (unique identifier)
  - `title`: Item title
  - `media_type`: movie or show
  - `tmdb_id`, `tvdb_id`, `imdb_id`: Provider IDs
  - `target_service`: sonarr or radarr
  - `status`: success, failed, or skipped
  - `synced_at`: Timestamp
  - `error_message`: Error details if failed

## Performance Optimization

### Metadata Caching

Lumarr caches Plex metadata for 7 days by default (configurable via `cache_max_age_days`). This significantly reduces API calls:

- **RSS Feed**: 1 HTTP request for any watchlist size
- **API (first run)**: 2 requests (overview + batch metadata)
- **API (subsequent runs)**: 1 request (metadata cached for 7 days)

### Follow Mode Intervals

When using follow mode (`lumarr sync --follow`), you can configure separate sync intervals:

- `plex.sync_interval`: How often to check Plex watchlist (default: 5 seconds)
- `letterboxd.sync_interval`: How often to check Letterboxd (default: 30 seconds)

Letterboxd scraping is slower, so a longer interval is recommended.
