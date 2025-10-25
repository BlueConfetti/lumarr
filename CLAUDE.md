# Agent Notes for Lumarr

This repository contains a Python CLI (`lumarr`) that syncs Plex watchlists with Sonarr/Radarr and can also scrape Letterboxd data. Keep these points in mind when working on the project:

## Working With the CLI
- The CLI is implemented with Click (`src/lumarr/cli.py`). Always invoke commands through the `lumarr` entry point (or `python -m lumarr.cli …`) so Click performs argument parsing; calling command functions directly will bypass required setup.
- Configuration defaults are resolved inside helper functions such as `_resolve_letterboxd_usernames()` and `_resolve_letterboxd_watchlists()`. Attempting to inject defaults via `ctx.default_map` proved unreliable with our entry point, so rely on those helpers instead of modifying Click internals.
- The `lbox` subcommands support `--rss/-r` (watched feed) and `--watchlist/-w` (scraped pages). Both flags accept multiple values, and the corresponding arrays can be set in `config.yaml` under `letterboxd.rss` and `letterboxd.watchlist`.

## Letterboxd Scraping Behaviour
- Watchlist scraping relies solely on the HTML returned from `https://letterboxd.com/<username>/watchlist/page/<n>/`. Each `LazyPoster` element already contains:
  - `data-item-name` / `data-item-full-display-name` → title + year
  - `data-film-id` → Letterboxd’s numeric film identifier (used as TMDB ID)
  - `data-item-slug` / `data-item-link` → canonical slug
- No extra requests (film pages, JSON endpoints, TMDB lookups) are issued for default behaviour. This keeps the flow to one HTTP request per page and avoids rate-limit issues.
- The RSS path remains unchanged: it parses provider IDs embedded in the feed and does not depend on additional services.

## ID Handling
- For watchlist items, `data-film-id` is treated as the TMDB ID. Do not try to enrich the data by calling TMDB or fetching film pages unless explicitly requested.
- For RSS entries, provider IDs are taken from the feed (`tmdb://`, `tvdb://`, `imdb://`). Existing logic in `SyncManager` still uses TMDB only if a key is configured and enrichment is necessary.

## Miscellaneous Notes
- Click will treat extra positional arguments as errors; if you need to add new options ensure they are properly defined on the command and don’t rely on `ctx.args`.
- All Letterboxd fetches use a small retry helper to handle HTTP 429 responses. When scraping, respect the existing delay/retry mechanics rather than lowering the interval.
- When updating documentation, keep README and `config.example.yaml` aligned with the supported flags (`--watchlist`, `--rss`) and configuration keys.

Following these guidelines will prevent regressions in the scraping flow and keep the CLI experience consistent.***
