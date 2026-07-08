"""
SQLite-based storage module for tracking seen content.

Provides a thread-safe ContentStorage class that persists content records
to a local SQLite database, enabling deduplication across polling cycles.
"""

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

logger = logging.getLogger(__name__)


class ContentStorage:
    """Thread-safe SQLite storage for tracking processed content.

    Stores records of all content items the agent has already seen and
    analyzed, preventing duplicate notifications across polling cycles.

    Attributes:
        db_path: Filesystem path to the SQLite database file.
    """

    _CREATE_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS seen_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            content_id TEXT NOT NULL UNIQUE,
            url TEXT,
            title TEXT,
            content_type TEXT,
            summary TEXT DEFAULT '',
            analyzed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            raw_data TEXT DEFAULT '{}'
        )
    """

    _CREATE_INDEX_SQL = """
        CREATE INDEX IF NOT EXISTS idx_platform_content
        ON seen_content (platform, content_id)
    """

    def __init__(self, db_path: str = "data/content_history.db", firebase_cred_path: str = "") -> None:
        """Initialise storage, creating the database directory and table.

        Args:
            db_path: Path to the SQLite database file.  Parent directories
                are created automatically if they do not exist.
            firebase_cred_path: Optional path to Firebase service account JSON.
        """
        self.db_path = db_path
        self.db = None

        if firebase_cred_path:
            if not os.path.exists(firebase_cred_path) and os.path.exists(f"/etc/secrets/{firebase_cred_path}"):
                firebase_cred_path = f"/etc/secrets/{firebase_cred_path}"

        if firebase_cred_path and os.path.exists(firebase_cred_path):
            try:
                if not firebase_admin._apps:
                    cred = credentials.Certificate(firebase_cred_path)
                    firebase_admin.initialize_app(cred)
                self.db = firestore.client()
                logger.info("✅ Firebase Firestore successfully initialized!")
            except Exception as exc:
                logger.error("❌ Failed to initialize Firebase: %s", exc)

        # Ensure the parent directory exists.
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        # Create the table on first run.
        try:
            with self._connect() as conn:
                conn.execute(self._CREATE_TABLE_SQL)
                conn.execute(self._CREATE_INDEX_SQL)
                conn.commit()
            logger.info("Storage initialised at %s", self.db_path)
        except sqlite3.Error as exc:
            logger.error("Failed to initialise database: %s", exc)
            raise

    # ------------------------------------------------------------------
    # Connection helper
    # ------------------------------------------------------------------

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        """Yield a SQLite connection with *check_same_thread=False*.

        The connection is closed automatically when the context exits.
        """
        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            yield conn
        finally:
            if conn is not None:
                conn.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_seen(self, platform: str, content_id: str) -> bool:
        """Check whether a content item has already been processed.

        Args:
            platform: Platform identifier (e.g. ``"youtube"``).
            content_id: Unique content identifier on that platform.

        Returns:
            ``True`` if the item exists in the database, ``False`` otherwise.
        """
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM seen_content WHERE platform = ? AND content_id = ?",
                    (platform, content_id),
                )
                return cursor.fetchone() is not None
        except sqlite3.Error as exc:
            logger.error("Error checking seen status: %s", exc)
            return False

    def mark_seen(
        self,
        platform: str,
        content_id: str,
        url: str,
        title: str,
        content_type: str,
        summary: str = "",
        raw_data: dict[str, Any] | None = None,
    ) -> None:
        """Record a content item as processed.

        Args:
            platform: Platform identifier (e.g. ``"youtube"``).
            content_id: Unique content identifier on that platform.
            url: Canonical URL of the content.
            title: Human-readable title.
            content_type: Content category (e.g. ``"video"``, ``"post"``).
            summary: Optional AI-generated summary.
            raw_data: Optional dictionary of raw API response data.
        """
        raw_json = json.dumps(raw_data) if raw_data else "{}"
        analyzed_at = datetime.now(timezone.utc).isoformat()

        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO seen_content
                        (platform, content_id, url, title, content_type,
                         summary, analyzed_at, raw_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        platform,
                        content_id,
                        url,
                        title,
                        content_type,
                        summary,
                        analyzed_at,
                        raw_json,
                    ),
                )
                conn.commit()
            logger.debug(
                "Marked %s/%s as seen", platform, content_id
            )
            
            # Push to Firebase if configured
            if self.db:
                doc_ref = self.db.collection('seen_content').document(content_id)
                doc_ref.set({
                    "platform": platform,
                    "content_id": content_id,
                    "url": url,
                    "title": title,
                    "content_type": content_type,
                    "summary": summary,
                    "analyzed_at": analyzed_at,
                    "raw_data": raw_json,
                }, merge=True)
                logger.info("☁️ Pushed %s to Firebase Firestore", content_id)
                
        except sqlite3.Error as exc:
            logger.error("Error marking content as seen: %s", exc)

    def get_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return the most recently analysed content entries.

        Args:
            limit: Maximum number of rows to return.

        Returns:
            A list of dictionaries, newest first.
        """
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    SELECT id, platform, content_id, url, title,
                           content_type, summary, analyzed_at, raw_data
                    FROM seen_content
                    ORDER BY analyzed_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
                rows = cursor.fetchall()

            results: list[dict[str, Any]] = []
            for row in rows:
                entry = dict(row)
                # Deserialise raw_data back to a dict.
                try:
                    entry["raw_data"] = json.loads(entry.get("raw_data", "{}"))
                except (json.JSONDecodeError, TypeError):
                    entry["raw_data"] = {}
                results.append(entry)

            return results
        except sqlite3.Error as exc:
            logger.error("Error fetching recent content: %s", exc)
            return []

    def get_stats(self) -> dict[str, int]:
        """Return content counts grouped by platform.

        Returns:
            A dictionary mapping platform names to their row counts,
            plus a ``"total"`` key with the overall count.

        Example::

            {"youtube": 42, "twitter": 7, "total": 49}
        """
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    SELECT platform, COUNT(*) as count
                    FROM seen_content
                    GROUP BY platform
                    """
                )
                rows = cursor.fetchall()

            stats: dict[str, int] = {row["platform"]: row["count"] for row in rows}
            stats["total"] = sum(stats.values())
            return stats
        except sqlite3.Error as exc:
            logger.error("Error fetching stats: %s", exc)
            return {"total": 0}
