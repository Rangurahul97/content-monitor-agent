"""Twitter / X profile monitor using Apify.

Fetches the latest tweets from a Twitter profile using the Apify API.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from apify_client import ApifyClient
from utils.logger import get_logger

logger = get_logger(__name__)

class TwitterMonitor:
    """Monitor a Twitter profile for new tweets.

    Uses Apify to bypass Twitter's aggressive scraping blocks.

    Args:
        username: The Twitter handle to monitor (without ``@``).
        api_token: Apify API token.
    """

    def __init__(self, username: str, api_token: str) -> None:
        self.username: str = username
        self.client = ApifyClient(api_token) if api_token else None

    def fetch_latest(self) -> list[dict[str, Any]]:
        """Fetch the latest tweets from the monitored profile."""
        if not self.client:
            logger.warning("Apify API token not provided, skipping Twitter monitor.")
            return []

        logger.info("Fetching Twitter feed for @%s via Apify...", self.username)

        # Prepare the Actor input
        run_input = {
            "handle": [self.username],
            "tweetsDesired": 10,
            "addUserInfo": False,
            "startUrls": [],
            "proxyConfig": {"useApifyProxy": True}
        }

        try:
            # Run the Actor (quacker/twitter-scraper)
            run = self.client.actor("quacker/twitter-scraper").call(run_input=run_input)
            
            # Fetch and parse Actor results from the run's dataset
            results = []
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                results.append(self._parse_item(item))
            
            logger.info("Parsed %d tweets for @%s", len(results), self.username)
            return results
            
        except Exception as e:
            logger.error("Failed to fetch Twitter data via Apify: %s", e)
            return []

    def _parse_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """Parse a single Apify tweet item into the standard schema."""
        full_text = item.get("full_text", "")
        tweet_id = item.get("id", "")
        content_id = tweet_id or hashlib.md5(full_text.encode()).hexdigest()
        
        url = item.get("url") or f"https://twitter.com/{self.username}/status/{tweet_id}"
        
        # Parse timestamp
        created_at = item.get("created_at")
        if created_at:
            try:
                # Typically format: "Mon Jul 08 14:30:00 +0000 2026" or ISO
                # We'll just fallback if parse fails
                dt = datetime.strptime(created_at, '%a %b %d %H:%M:%S +0000 %Y')
                published_at = dt.replace(tzinfo=timezone.utc).isoformat()
            except ValueError:
                published_at = datetime.now(timezone.utc).isoformat()
        else:
            published_at = datetime.now(timezone.utc).isoformat()
            
        # Extract media
        media = item.get("extended_entities", {}).get("media", [])
        media_urls = [m.get("media_url_https") for m in media if "media_url_https" in m]
        thumbnail = media_urls[0] if media_urls else ""
        
        # Detect threads (basic heuristic)
        is_reply = bool(item.get("in_reply_to_status_id"))
        content_type = "thread" if is_reply else "tweet"
        
        title = full_text[:120].strip() if full_text else "New Tweet"

        return {
            "platform": "twitter",
            "content_id": content_id,
            "content_type": content_type,
            "title": title,
            "description": full_text,
            "url": url,
            "thumbnail": thumbnail,
            "published_at": published_at,
            "extra": {
                "username": self.username,
                "media_urls": media_urls,
                "raw_data": item,
            },
        }
