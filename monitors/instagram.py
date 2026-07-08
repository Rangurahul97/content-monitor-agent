"""Instagram profile monitor using Apify.

Fetches the latest reels and posts from an Instagram profile.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from apify_client import ApifyClient
from utils.logger import get_logger

logger = get_logger(__name__)

class InstagramMonitor:
    """Monitor an Instagram profile for new posts/reels.

    Uses Apify to bypass Instagram's aggressive scraping blocks.

    Args:
        username: The Instagram handle to monitor (without ``@``).
        api_token: Apify API token.
    """

    def __init__(self, username: str, api_token: str) -> None:
        self.username: str = username
        self.client = ApifyClient(api_token) if api_token else None

    def fetch_latest(self) -> list[dict[str, Any]]:
        """Fetch the latest posts from the monitored profile."""
        if not self.client:
            logger.warning("Apify API token not provided, skipping Instagram monitor.")
            return []

        logger.info("Fetching Instagram feed for @%s via Apify...", self.username)

        # Prepare the Actor input
        run_input = {
            "usernames": [self.username],
            "resultsLimit": 10
        }

        try:
            # Run the Actor (apify/instagram-profile-scraper)
            run = self.client.actor("apify/instagram-profile-scraper").call(run_input=run_input)
            
            # Fetch and parse Actor results from the run's dataset
            results = []
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                results.append(self._parse_item(item))
            
            logger.info("Parsed %d posts for Instagram @%s", len(results), self.username)
            return results
            
        except Exception as e:
            logger.error("Failed to fetch Instagram data via Apify: %s", e)
            return []

    def _parse_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """Parse a single Apify instagram item into the standard schema."""
        caption = item.get("caption", "")
        post_id = item.get("id", "")
        content_id = post_id or hashlib.md5(caption.encode()).hexdigest()
        
        url = item.get("url") or f"https://instagram.com/p/{item.get('shortCode', '')}"
        
        # Parse timestamp
        timestamp = item.get("timestamp")
        if timestamp:
            try:
                # Typically ISO format
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                published_at = dt.replace(tzinfo=timezone.utc).isoformat()
            except ValueError:
                published_at = datetime.now(timezone.utc).isoformat()
        else:
            published_at = datetime.now(timezone.utc).isoformat()
            
        # Extract media
        thumbnail = item.get("displayUrl", "")
        media_url = item.get("videoUrl", "") or item.get("displayUrl", "")
        
        # Content type
        is_video = item.get("isVideo", False)
        content_type = "reel" if is_video else "post"
        
        title = caption[:120].strip() if caption else f"New Instagram {content_type.capitalize()}"

        return {
            "platform": "instagram",
            "content_id": content_id,
            "content_type": content_type,
            "title": title,
            "description": caption,
            "url": url,
            "thumbnail": thumbnail,
            "published_at": published_at,
            "extra": {
                "username": self.username,
                "media_url": media_url,
                "raw_data": item,
            },
        }
