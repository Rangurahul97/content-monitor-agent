"""YouTube channel monitor.

Fetches the latest videos and Shorts from a YouTube channel via its public
RSS feed and optionally retrieves transcripts for downstream analysis.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import feedparser  # type: ignore[import-untyped]
import requests
from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore[import-untyped]

from utils.logger import get_logger

logger = get_logger(__name__)

# YouTube constructs thumbnail URLs from the video ID.
_THUMBNAIL_TEMPLATE = "https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
_RSS_FEED_TEMPLATE = (
    "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
)
_VIDEO_URL_TEMPLATE = "https://www.youtube.com/watch?v={video_id}"

# Heuristics for detecting Shorts when the Data API is unavailable.
_SHORT_TITLE_KEYWORDS: list[str] = ["#shorts", "#short"]


class YouTubeMonitor:
    """Monitor a YouTube channel for new content.

    The primary data source is the channel's public Atom/RSS feed, which
    requires **no** API key.  An optional YouTube Data API v3 key can be
    supplied to enrich entries with duration metadata (used to distinguish
    regular videos from Shorts).

    Args:
        channel_id: The YouTube channel ID (e.g. ``UCxxxxxxxxxxxxxxxxxxxxxx``).
        api_key: Optional YouTube Data API v3 key for duration look-ups.
        analyze_transcripts: Whether :meth:`get_transcript` should be called
            for every video returned by :meth:`fetch_latest`.
        max_transcript_chars: Maximum character count for returned transcripts.
    """

    def __init__(
        self,
        channel_id: str,
        api_key: str | None = None,
        analyze_transcripts: bool = True,
        max_transcript_chars: int = 15_000,
    ) -> None:
        self.channel_id: str = channel_id
        self.api_key: str | None = api_key
        self.analyze_transcripts: bool = analyze_transcripts
        self.max_transcript_chars: int = max_transcript_chars

        self._feed_url: str = _RSS_FEED_TEMPLATE.format(channel_id=channel_id)
        self._session: requests.Session = requests.Session()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_latest(self) -> list[dict[str, Any]]:
        """Fetch the latest videos from the channel's RSS feed.

        Returns:
            A list of content dicts conforming to the standard monitor
            schema.  Returns an empty list when the feed cannot be reached
            or parsed.
        """
        logger.info("Fetching YouTube RSS feed for channel %s", self.channel_id)

        try:
            response = self._session.get(self._feed_url, timeout=15)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Failed to fetch RSS feed: %s", exc)
            return []

        feed = feedparser.parse(response.text)

        if feed.bozo and not feed.entries:
            logger.error("RSS feed parse error: %s", feed.bozo_exception)
            return []

        results: list[dict[str, Any]] = []
        for entry in feed.entries:
            try:
                parsed = self._parse_feed_entry(entry)
                results.append(parsed)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Skipping entry due to parse error: %s", exc)

        logger.info("Parsed %d videos from RSS feed", len(results))

        # Optionally attach transcripts.
        if self.analyze_transcripts:
            for item in results:
                video_id = item["content_id"]
                transcript = self.get_transcript(video_id)
                item["extra"]["transcript"] = transcript

        return results

    def get_transcript(self, video_id: str) -> str | None:
        """Fetch the transcript for a single YouTube video.

        Attempts to retrieve an English transcript first, then falls back to
        any available language.

        Args:
            video_id: The YouTube video ID (e.g. ``dQw4w9WgXcQ``).

        Returns:
            The concatenated transcript text truncated to
            :attr:`max_transcript_chars`, or ``None`` when no transcript is
            available.
        """
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            # Prefer English; fall back to whatever is available.
            transcript = None
            try:
                transcript = transcript_list.find_transcript(["en"])
            except Exception:  # noqa: BLE001
                try:
                    transcript = transcript_list.find_generated_transcript(["en"])
                except Exception:  # noqa: BLE001
                    # Pick the first available transcript in any language.
                    for t in transcript_list:
                        transcript = t
                        break

            if transcript is None:
                logger.debug("No transcript found for video %s", video_id)
                return None

            segments = transcript.fetch()
            full_text = " ".join(
                seg.get("text", "") for seg in segments
            ).strip()

            if not full_text:
                return None

            truncated = full_text[: self.max_transcript_chars]
            logger.debug(
                "Transcript for %s: %d chars (truncated=%s)",
                video_id,
                len(full_text),
                len(full_text) > self.max_transcript_chars,
            )
            return truncated

        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "Could not retrieve transcript for %s: %s", video_id, exc
            )
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_feed_entry(self, entry: Any) -> dict[str, Any]:
        """Parse a single ``feedparser`` entry into the standard schema.

        Args:
            entry: A :class:`feedparser.FeedParserDict` entry object.

        Returns:
            A dict with the standard monitor keys.
        """
        # The RSS feed stores the video ID in the ``yt_videoid`` attribute.
        video_id: str = getattr(entry, "yt_videoid", "") or entry.get(
            "yt_videoid", ""
        )

        # Fallback: extract from the link URL.
        if not video_id and hasattr(entry, "link"):
            video_id = entry.link.rsplit("v=", 1)[-1]

        title: str = entry.get("title", "")
        link: str = entry.get("link", _VIDEO_URL_TEMPLATE.format(video_id=video_id))
        author: str = entry.get("author", "")
        summary: str = entry.get("summary", "")

        # Parse published date into ISO-8601 string.
        published_parsed = entry.get("published_parsed")
        if published_parsed:
            published_at = (
                datetime(*published_parsed[:6], tzinfo=timezone.utc).isoformat()
            )
        else:
            published_at = entry.get("published", datetime.now(timezone.utc).isoformat())

        # Detect Shorts heuristically (title keywords).
        content_type = self._detect_content_type(title, video_id)

        thumbnail_url = _THUMBNAIL_TEMPLATE.format(video_id=video_id)

        return {
            "platform": "youtube",
            "content_id": video_id,
            "content_type": content_type,
            "title": title,
            "description": summary,
            "url": link,
            "thumbnail": thumbnail_url,
            "published_at": published_at,
            "extra": {
                "author": author,
                "channel_id": self.channel_id,
            },
        }

    def _detect_content_type(self, title: str, video_id: str) -> str:
        """Guess whether a video is a Short or a regular video.

        Uses title keyword heuristics first.  If a YouTube Data API key is
        configured, falls back to checking the video duration (< 60 s →
        Short).

        Args:
            title: The video title.
            video_id: The YouTube video ID.

        Returns:
            ``'short'`` or ``'video'``.
        """
        lower_title = title.lower()
        if any(kw in lower_title for kw in _SHORT_TITLE_KEYWORDS):
            return "short"

        if self.api_key:
            try:
                duration_s = self._get_duration_seconds(video_id)
                if duration_s is not None and duration_s < 60:
                    return "short"
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "Duration lookup failed for %s: %s", video_id, exc
                )

        return "video"

    def _get_duration_seconds(self, video_id: str) -> int | None:
        """Fetch the video duration via the YouTube Data API v3.

        Args:
            video_id: The YouTube video ID.

        Returns:
            Duration in seconds, or ``None`` on failure.
        """
        if not self.api_key:
            return None

        url = (
            "https://www.googleapis.com/youtube/v3/videos"
            f"?part=contentDetails&id={video_id}&key={self.api_key}"
        )
        try:
            resp = self._session.get(url, timeout=10)
            resp.raise_for_status()
            items = resp.json().get("items", [])
            if not items:
                return None

            duration_iso = items[0]["contentDetails"]["duration"]  # e.g. PT1M30S
            return self._iso8601_duration_to_seconds(duration_iso)
        except Exception as exc:  # noqa: BLE001
            logger.debug("API duration request failed: %s", exc)
            return None

    @staticmethod
    def _iso8601_duration_to_seconds(duration: str) -> int:
        """Convert an ISO 8601 duration string (e.g. ``PT1M30S``) to seconds.

        Args:
            duration: ISO 8601 duration string.

        Returns:
            Total seconds.
        """
        import re

        match = re.match(
            r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration
        )
        if not match:
            return 0

        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        return hours * 3600 + minutes * 60 + seconds
