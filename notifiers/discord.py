"""Discord notification module using webhook embeds.

Sends rich embed messages to a Discord channel via an incoming webhook
URL, with per-platform colours and structured analysis fields.
"""

from datetime import datetime, timezone
from typing import Any

import requests

from utils.logger import get_logger

logger = get_logger(__name__)


class DiscordNotifier:
    """Sends content analysis notifications to Discord via webhooks.

    Messages are delivered as rich embeds with colour-coded platform
    indicators, structured fields for analysis data, and footer
    timestamps.

    Attributes:
        webhook_url: The full Discord webhook URL.
    """

    _PLATFORM_COLORS: dict[str, int] = {
        "youtube": 0xFF0000,
        "instagram": 0xE1306C,
        "twitter": 0x1DA1F2,
    }

    _PLATFORM_EMOJIS: dict[str, str] = {
        "youtube": "📺",
        "instagram": "📸",
        "twitter": "🐦",
    }

    def __init__(self, webhook_url: str) -> None:
        """Initialize the Discord notifier.

        Args:
            webhook_url: Discord incoming webhook URL.
        """
        self.webhook_url: str = webhook_url
        logger.info("DiscordNotifier initialized.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send(self, content: dict[str, Any], analysis: dict[str, Any]) -> bool:
        """Send a rich embed notification to Discord.

        Args:
            content: Content metadata dictionary with keys:
                - ``platform`` (str)
                - ``content_type`` (str)
                - ``title`` (str)
                - ``url`` (str)
                - ``published_at`` (str)
                - ``target_name`` (str, optional)
                - ``thumbnail_url`` (str, optional)
            analysis: Analysis result dictionary with keys:
                - ``summary`` (str)
                - ``key_topics`` (list[str])
                - ``key_takeaways`` (list[str])
                - ``content_category`` (str)
                - ``importance_score`` (int)
                - ``sentiment`` (str)

        Returns:
            ``True`` if the webhook call succeeds, ``False`` otherwise.
        """
        payload = self._build_payload(content, analysis)
        return self._send_webhook(payload)

    # ------------------------------------------------------------------
    # Payload construction
    # ------------------------------------------------------------------

    def _build_payload(
        self,
        content: dict[str, Any],
        analysis: dict[str, Any],
    ) -> dict[str, Any]:
        """Build the Discord webhook JSON payload with an embed.

        Args:
            content: Content metadata dictionary.
            analysis: Analysis result dictionary.

        Returns:
            A dictionary ready to be serialised as the webhook JSON body.
        """
        platform: str = content.get("platform", "unknown").lower()
        content_type: str = content.get("content_type", "content")
        title: str = content.get("title", "Untitled")
        url: str = content.get("url", "")
        published_at: str = content.get("published_at", "N/A")
        target_name: str = content.get("target_name", "Unknown")
        thumbnail_url: str | None = content.get("thumbnail_url")

        platform_emoji: str = self._PLATFORM_EMOJIS.get(platform, "📌")
        color: int = self._PLATFORM_COLORS.get(platform, 0x6C63FF)

        summary: str = analysis.get("summary", "N/A")
        key_topics: list[str] = analysis.get("key_topics", [])
        key_takeaways: list[str] = analysis.get("key_takeaways", [])
        content_category: str = analysis.get("content_category", "N/A")
        importance_score: int = analysis.get("importance_score", 5)
        sentiment: str = analysis.get("sentiment", "neutral")

        topics_value: str = (
            "\n".join(f"• {t}" for t in key_topics) or "N/A"
        )
        takeaways_value: str = (
            "\n".join(f"• {t}" for t in key_takeaways) or "N/A"
        )

        importance_bar = "🟩" * importance_score + "⬛" * (10 - importance_score)

        embed: dict[str, Any] = {
            "title": f"{platform_emoji} {title}",
            "url": url,
            "description": (
                f"🔔 **New {platform.capitalize()} {content_type.capitalize()}**\n"
                f"👤 **{target_name}** · 📅 {published_at}\n\n"
                f"📋 **Summary**\n{summary}"
            ),
            "color": color,
            "fields": [
                {
                    "name": "🎯 Key Topics",
                    "value": topics_value,
                    "inline": True,
                },
                {
                    "name": "💡 Key Takeaways",
                    "value": takeaways_value,
                    "inline": True,
                },
                {
                    "name": "📊 Category",
                    "value": content_category.capitalize(),
                    "inline": True,
                },
                {
                    "name": "🔥 Importance",
                    "value": f"**{importance_score}/10**\n{importance_bar}",
                    "inline": True,
                },
                {
                    "name": "💭 Sentiment",
                    "value": sentiment.capitalize(),
                    "inline": True,
                },
            ],
            "footer": {
                "text": "Content Monitor Agent",
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if thumbnail_url:
            embed["thumbnail"] = {"url": thumbnail_url}

        return {"embeds": [embed]}

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def _send_webhook(self, payload: dict[str, Any]) -> bool:
        """POST the payload to the Discord webhook URL.

        Args:
            payload: JSON-serialisable dictionary for the webhook body.

        Returns:
            ``True`` on a 2xx response, ``False`` otherwise.
        """
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=15,
            )

            if response.status_code == 204:
                # Discord returns 204 No Content on success.
                logger.info("Discord webhook message sent successfully.")
                return True

            if response.ok:
                logger.info(
                    "Discord webhook accepted (status %d).",
                    response.status_code,
                )
                return True

            logger.error(
                "Discord webhook failed: %d %s — %s",
                response.status_code,
                response.reason,
                response.text[:300],
            )
            return False

        except requests.RequestException:
            logger.exception("Failed to send Discord webhook message.")
            return False
