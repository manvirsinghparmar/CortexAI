"""Thread-safe TTL cache for research results."""
import hashlib
import threading
from typing import Optional, Any, Dict, Tuple
from datetime import datetime, timedelta


class InMemoryTTLCache:
    """
    Thread-safe in-memory cache with TTL (Time To Live).

    Uses sha256 hash of text as key (first 16 chars) and threading.Lock
    for concurrent access safety under FastAPI.
    """

    def __init__(self, ttl_seconds: int):
        """
        Initialize cache with TTL.

        Args:
            ttl_seconds: Time to live in seconds for cached entries
        """
        self._cache: Dict[str, Tuple[Any, datetime]] = {}
        self._lock = threading.Lock()  # Required for FastAPI concurrency
        self._ttl = timedelta(seconds=ttl_seconds)

    def _make_key(self, text: str) -> str:
        """Generate cache key from text using sha256 hash."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def get(self, text: str) -> Optional[Any]:
        """
        Get cached value if exists and not expired.

        Args:
            text: Text to use as cache key

        Returns:
            Cached value if exists and valid, None otherwise
        """
        key = self._make_key(text)
        with self._lock:  # Lock around access
            if key in self._cache:
                value, expiry = self._cache[key]
                if datetime.utcnow() < expiry:
                    return value
                # Expired - remove it
                del self._cache[key]
            return None

    def set(self, text: str, value: Any):
        """
        Store value in cache with TTL.

        Args:
            text: Text to use as cache key
            value: Value to cache
        """
        key = self._make_key(text)
        with self._lock:  # Lock around access
            self._cache[key] = (value, datetime.utcnow() + self._ttl)

    def clear(self):
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
