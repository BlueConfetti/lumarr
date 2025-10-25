"""Database operations for tracking synced items."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from .models import MediaType, RequestStatus


class Database:
    """SQLite database for tracking synced watchlist items."""

    def __init__(self, db_path: str):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self):
        """Create database tables if they don't exist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS synced_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rating_key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    tmdb_id TEXT,
                    tvdb_id TEXT,
                    imdb_id TEXT,
                    target_service TEXT NOT NULL,
                    status TEXT NOT NULL,
                    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    error_message TEXT,
                    UNIQUE(rating_key, target_service)
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_rating_key
                ON synced_items(rating_key)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tmdb_id
                ON synced_items(tmdb_id)
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS watchlist_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rating_key TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_baseline INTEGER DEFAULT 0
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_watchlist_rating_key
                ON watchlist_items(rating_key)
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metadata_cache (
                    rating_key TEXT PRIMARY KEY,
                    metadata_json TEXT NOT NULL,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_metadata_cache_cached_at
                ON metadata_cache(cached_at)
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS letterboxd_metadata (
                    letterboxd_id TEXT PRIMARY KEY,
                    slug TEXT NOT NULL,
                    tmdb_id TEXT,
                    title TEXT,
                    year INTEGER,
                    fetched_at TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_letterboxd_slug
                ON letterboxd_metadata(slug)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_letterboxd_tmdb_id
                ON letterboxd_metadata(tmdb_id)
            """)
            conn.commit()

    @contextmanager
    def get_connection(self):
        """Get database connection context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def is_synced(self, rating_key: str, target_service: str) -> bool:
        """Check if item has already been synced successfully.

        Args:
            rating_key: Plex rating key
            target_service: Target service (sonarr/radarr)

        Returns:
            True if item was previously synced successfully
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) as count
                FROM synced_items
                WHERE rating_key = ?
                AND target_service = ?
                AND status = ?
                """,
                (rating_key, target_service, RequestStatus.SUCCESS.value)
            )
            row = cursor.fetchone()
            return row["count"] > 0

    def record_sync(
        self,
        rating_key: str,
        title: str,
        media_type: MediaType,
        target_service: str,
        status: RequestStatus,
        tmdb_id: Optional[str] = None,
        tvdb_id: Optional[str] = None,
        imdb_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        """Record a sync operation.

        Args:
            rating_key: Plex rating key
            title: Item title
            media_type: Type of media
            target_service: Target service (sonarr/radarr)
            status: Sync status
            tmdb_id: TMDB ID if available
            tvdb_id: TVDB ID if available
            imdb_id: IMDB ID if available
            error_message: Error message if failed
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO synced_items
                (rating_key, title, media_type, tmdb_id, tvdb_id, imdb_id,
                 target_service, status, synced_at, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rating_key,
                    title,
                    media_type.value,
                    tmdb_id,
                    tvdb_id,
                    imdb_id,
                    target_service,
                    status.value,
                    datetime.now().isoformat(),
                    error_message,
                ),
            )
            conn.commit()

    def get_sync_history(self, limit: int = 50):
        """Get recent sync history.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of sync history records
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM synced_items
                ORDER BY synced_at DESC
                LIMIT ?
                """,
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def clear_history(self):
        """Clear all sync history."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM synced_items")
            conn.commit()

    def mark_watchlist_item_seen(
        self,
        rating_key: str,
        title: str,
        media_type: MediaType,
        is_baseline: bool = False,
    ):
        """Mark a watchlist item as seen.

        Args:
            rating_key: Plex rating key
            title: Item title
            media_type: Type of media
            is_baseline: Whether this is a baseline item
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO watchlist_items
                (rating_key, title, media_type, is_baseline)
                VALUES (?, ?, ?, ?)
                """,
                (rating_key, title, media_type.value, 1 if is_baseline else 0),
            )
            conn.commit()

    def is_baseline_item(self, rating_key: str) -> bool:
        """Check if an item was part of the baseline watchlist.

        Args:
            rating_key: Plex rating key

        Returns:
            True if item is marked as baseline
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT is_baseline
                FROM watchlist_items
                WHERE rating_key = ?
                """,
                (rating_key,)
            )
            row = cursor.fetchone()
            return row and row["is_baseline"] == 1

    def is_seen(self, rating_key: str) -> bool:
        """Check if an item has been seen in the watchlist before.

        Args:
            rating_key: Plex rating key

        Returns:
            True if item has been seen before
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) as count
                FROM watchlist_items
                WHERE rating_key = ?
                """,
                (rating_key,)
            )
            row = cursor.fetchone()
            return row["count"] > 0

    def get_metadata_cache(self, rating_key: str) -> Optional[Dict]:
        """Get cached metadata for a rating key.

        Args:
            rating_key: Plex rating key

        Returns:
            Cached metadata dict or None if not cached
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT metadata_json, cached_at
                FROM metadata_cache
                WHERE rating_key = ?
                """,
                (rating_key,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "metadata": json.loads(row["metadata_json"]),
                    "cached_at": row["cached_at"]
                }
            return None

    def get_multiple_metadata_cache(self, rating_keys: List[str]) -> Dict[str, Dict]:
        """Get cached metadata for multiple rating keys.

        Args:
            rating_keys: List of Plex rating keys

        Returns:
            Dict mapping rating_key to metadata dict
        """
        if not rating_keys:
            return {}

        with self.get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(rating_keys))
            cursor.execute(
                f"""
                SELECT rating_key, metadata_json, cached_at
                FROM metadata_cache
                WHERE rating_key IN ({placeholders})
                """,
                rating_keys
            )
            result = {}
            for row in cursor.fetchall():
                result[row["rating_key"]] = {
                    "metadata": json.loads(row["metadata_json"]),
                    "cached_at": row["cached_at"]
                }
            return result

    def set_metadata_cache(self, rating_key: str, metadata: Dict):
        """Store metadata in cache.

        Args:
            rating_key: Plex rating key
            metadata: Metadata dict to cache
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO metadata_cache
                (rating_key, metadata_json, cached_at)
                VALUES (?, ?, ?)
                """,
                (rating_key, json.dumps(metadata), datetime.now().isoformat())
            )
            conn.commit()

    def set_multiple_metadata_cache(self, metadata_dict: Dict[str, Dict]):
        """Store multiple metadata items in cache.

        Args:
            metadata_dict: Dict mapping rating_key to metadata dict
        """
        if not metadata_dict:
            return

        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            data = [
                (rating_key, json.dumps(metadata), now)
                for rating_key, metadata in metadata_dict.items()
            ]
            cursor.executemany(
                """
                INSERT OR REPLACE INTO metadata_cache
                (rating_key, metadata_json, cached_at)
                VALUES (?, ?, ?)
                """,
                data
            )
            conn.commit()

    def is_cache_stale(self, rating_key: str, max_age_days: int = 7) -> bool:
        """Check if cached metadata is stale.

        Args:
            rating_key: Plex rating key
            max_age_days: Maximum age in days before considering stale

        Returns:
            True if cache is stale or doesn't exist
        """
        cached = self.get_metadata_cache(rating_key)
        if not cached:
            return True

        cached_at = datetime.fromisoformat(cached["cached_at"])
        age = datetime.now() - cached_at
        return age > timedelta(days=max_age_days)

    def clear_metadata_cache(self):
        """Clear all metadata cache."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM metadata_cache")
            conn.commit()

    def clear_stale_cache(self, max_age_days: int = 30):
        """Clear cache entries older than specified days.

        Args:
            max_age_days: Clear entries older than this many days
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cutoff = (datetime.now() - timedelta(days=max_age_days)).isoformat()
            cursor.execute(
                """
                DELETE FROM metadata_cache
                WHERE cached_at < ?
                """,
                (cutoff,)
            )
            conn.commit()

    def get_letterboxd_metadata(self, letterboxd_id: str) -> Optional[Dict]:
        """Get cached Letterboxd metadata.

        Args:
            letterboxd_id: Letterboxd film ID

        Returns:
            Metadata dict or None if not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT letterboxd_id, slug, tmdb_id, title, year, fetched_at
                FROM letterboxd_metadata
                WHERE letterboxd_id = ?
                """,
                (letterboxd_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def set_letterboxd_metadata(
        self,
        letterboxd_id: str,
        slug: str,
        title: str,
        year: Optional[int] = None,
        tmdb_id: Optional[str] = None,
    ):
        """Store or update Letterboxd metadata.

        Args:
            letterboxd_id: Letterboxd film ID
            slug: Film slug
            title: Film title
            year: Release year
            tmdb_id: TMDB ID if available
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            fetched_at = datetime.now().isoformat() if tmdb_id else None
            cursor.execute(
                """
                INSERT OR REPLACE INTO letterboxd_metadata
                (letterboxd_id, slug, tmdb_id, title, year, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (letterboxd_id, slug, tmdb_id, title, year, fetched_at)
            )
            conn.commit()

    def update_letterboxd_tmdb_id(self, letterboxd_id: str, tmdb_id: str):
        """Update TMDB ID for a Letterboxd item.

        Args:
            letterboxd_id: Letterboxd film ID
            tmdb_id: TMDB ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE letterboxd_metadata
                SET tmdb_id = ?, fetched_at = ?
                WHERE letterboxd_id = ?
                """,
                (tmdb_id, datetime.now().isoformat(), letterboxd_id)
            )
            conn.commit()

    def get_letterboxd_by_slug(self, slug: str) -> Optional[Dict]:
        """Get Letterboxd metadata by slug.

        Args:
            slug: Film slug

        Returns:
            Metadata dict or None if not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT letterboxd_id, slug, tmdb_id, title, year, fetched_at
                FROM letterboxd_metadata
                WHERE slug = ?
                """,
                (slug,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
