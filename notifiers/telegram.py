"""Telegram notification module using the Telegram Bot HTTP API.

Sends beautifully formatted content analysis notifications,
startup messages, and error alerts to a Telegram chat.
"""

from typing import Any

import requests

from utils.logger import get_logger

logger = get_logger(__name__)


class TelegramNotifier:
    """Sends notifications to a Telegram chat via the Bot API.

    Uses direct HTTP POST requests to the Telegram Bot API (no async
    library dependency). Messages are formatted with HTML parse mode.

    Attributes:
        bot_token: The Telegram bot authentication token.
        chat_id: The target chat/channel ID for messages.
    """

    _API_BASE = "https://api.telegram.org/bot{token}/sendMessage"

    _PLATFORM_EMOJIS: dict[str, str] = {
        "youtube": "📺",
        "instagram": "📸",
        "twitter": "🐦",
    }

    def __init__(self, bot_token: str, chat_id: str) -> None:
        """Initialize the Telegram notifier.

        Args:
            bot_token: Telegram Bot API token (from @BotFather).
            chat_id: Numeric or string chat/channel ID to send messages to.
        """
        self.bot_token: str = bot_token
        self.chat_id: str = chat_id
        self._api_url: str = self._API_BASE.format(token=bot_token)
        logger.info("TelegramNotifier initialized for chat_id=%s", chat_id)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send(self, content: dict[str, Any], analysis: dict[str, Any]) -> bool:
        """Send a formatted content analysis notification.

        Args:
            content: Content metadata dictionary with keys:
                - ``platform`` (str)
                - ``content_type`` (str)
                - ``title`` (str)
                - ``url`` (str)
                - ``published_at`` (str)
                - ``target_name`` (str, optional)
            analysis: Analysis result dictionary with keys:
                - ``summary`` (str)
                - ``key_topics`` (list[str])
                - ``key_takeaways`` (list[str])
                - ``content_category`` (str)
                - ``importance_score`` (int)
                - ``sentiment`` (str)

        Returns:
            ``True`` if the message was sent successfully, ``False`` otherwise.
        """
        message = self._format_message(content, analysis)
        return self._send_message(message)

    def send_startup_message(self) -> bool:
        """Send a startup notification indicating the agent is online.

        Returns:
            ``True`` if the message was sent successfully, ``False`` otherwise.
        """
        message = (
            "🤖 <b>Content Monitor Agent is now ONLINE!</b>\n"
            "Monitoring for new content..."
        )
        return self._send_message(message)

    def send_error(self, error_msg: str) -> bool:
        """Send an error notification.

        Args:
            error_msg: Human-readable description of the error.

        Returns:
            ``True`` if the message was sent successfully, ``False`` otherwise.
        """
        message = f"⚠️ <b>Error:</b>\n<i>{self._escape_html(error_msg)}</i>"
        return self._send_message(message)

    # ------------------------------------------------------------------
    # Message formatting
    # ------------------------------------------------------------------

    def _format_message(
        self,
        content: dict[str, Any],
        analysis: dict[str, Any],
    ) -> str:
        """Build a richly-formatted HTML message for Telegram.

        Args:
            content: Content metadata dictionary.
            analysis: Analysis result dictionary.

        Returns:
            An HTML-formatted message string.
        """
        platform: str = content.get("platform", "unknown").lower()
        content_type: str = content.get("content_type", "content").upper()
        title: str = self._escape_html(content.get("title", "Untitled"))
        url: str = content.get("url", "")
        published_at: str = content.get("published_at", "N/A")
        target_name: str = self._escape_html(
            content.get("target_name", "Unknown")
        )

        platform_emoji = self._PLATFORM_EMOJIS.get(platform, "📌")
        platform_label = platform.upper()

        summary: str = self._escape_html(analysis.get("summary", "N/A"))
        key_topics: list[str] = analysis.get("key_topics", [])
        key_takeaways: list[str] = analysis.get("key_takeaways", [])
        content_category: str = analysis.get("content_category", "N/A")
        importance_score: int = analysis.get("importance_score", 5)
        sentiment: str = analysis.get("sentiment", "neutral")

        topics_block = "\n".join(
            f"  • {self._escape_html(t)}" for t in key_topics
        ) or "  • N/A"

        takeaways_block = "\n".join(
            f"  • {self._escape_html(t)}" for t in key_takeaways
        ) or "  • N/A"

        importance_bar = "🔥" * min(importance_score, 10)

        lines = [
            f"🔔 <b>NEW {platform_label} {content_type}</b>",
            "",
            f"{platform_emoji} <b>{title}</b>",
            f"👤 {target_name}",
            f"📅 {published_at}",
            "",
            f"📋 <b>Summary:</b>",
            f"{summary}",
            "",
            f"🎯 <b>Key Topics:</b>",
            topics_block,
            "",
            f"💡 <b>Key Takeaways:</b>",
            takeaways_block,
            "",
            f"📊 <b>Category:</b> {self._escape_html(content_category)}",
            f"🔥 <b>Importance:</b> {importance_score}/10 {importance_bar}",
            f"💭 <b>Sentiment:</b> {self._escape_html(sentiment)}",
            "",
            f'🔗 <a href="{url}">View Original</a>',
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def _send_message(
        self,
        text: str,
        disable_web_page_preview: bool = False,
    ) -> bool:
        """Send a message via the Telegram Bot API.

        Args:
            text: HTML-formatted message text.
            disable_web_page_preview: Whether to suppress link previews.

        Returns:
            ``True`` on HTTP 200 with ``ok: true``, ``False`` otherwise.
        """
        payload: dict[str, Any] = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": disable_web_page_preview,
        }

        try:
            response = requests.post(
                self._api_url,
                json=payload,
                timeout=15,
            )
            response.raise_for_status()

            result = response.json()
            if result.get("ok"):
                logger.info("Telegram message sent successfully.")
                return True

            logger.error(
                "Telegram API returned ok=false: %s",
                result.get("description", "unknown error"),
            )
            return False

        except requests.RequestException:
            logger.exception("Failed to send Telegram message.")
            return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _escape_html(text: str) -> str:
        """Escape HTML special characters for Telegram's HTML parse mode.

        Args:
            text: Raw text string.

        Returns:
            Text with ``<``, ``>``, ``&`` escaped.
        """
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
