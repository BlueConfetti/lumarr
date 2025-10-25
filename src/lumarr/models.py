"""Data models for Plex watchlist items."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class MediaType(Enum):
    """Type of media item."""
    MOVIE = "movie"
    TV_SHOW = "show"


class RequestStatus(Enum):
    """Status of a sync request."""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ProviderId:
    """Provider IDs for cross-referencing media across services."""
    tmdb_id: Optional[str] = None
    tvdb_id: Optional[str] = None
    imdb_id: Optional[str] = None


@dataclass
class WatchlistItem:
    """Item from Plex watchlist."""
    rating_key: str
    title: str
    media_type: MediaType
    year: Optional[int] = None
    guids: list[str] = None
    provider_ids: Optional[ProviderId] = None
    content_rating: Optional[str] = None
    summary: Optional[str] = None
    genres: list[str] = None
    studio: Optional[str] = None
    added_at: Optional[int] = None
    rating: Optional[float] = None
    letterboxd_id: Optional[str] = None
    letterboxd_slug: Optional[str] = None

    def __post_init__(self):
        if self.guids is None:
            self.guids = []
        if self.genres is None:
            self.genres = []


@dataclass
class SyncResult:
    """Result of syncing a single item."""
    item: WatchlistItem
    status: RequestStatus
    message: str
    target_service: str


@dataclass
class SyncSummary:
    """Summary of entire sync operation."""
    total: int = 0
    movies_added: int = 0
    shows_added: int = 0
    skipped: int = 0
    failed: int = 0
    results: list[SyncResult] = None

    def __post_init__(self):
        if self.results is None:
            self.results = []
