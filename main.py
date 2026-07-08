"""Content Monitor Agent — Main entry point.

Orchestrates platform monitors, AI analysis, and notification delivery
on a configurable polling schedule.  Run directly to start monitoring::

    python main.py
"""

from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

import yaml
from apscheduler.schedulers.blocking import BlockingScheduler

from analyzer.ai_engine import ContentAnalyzer
from database.storage import ContentStorage
from monitors.instagram import InstagramMonitor
from monitors.twitter import TwitterMonitor
from monitors.youtube import YouTubeMonitor
from notifiers.discord import DiscordNotifier
from notifiers.email_notify import EmailNotifier
from notifiers.telegram import TelegramNotifier
from utils.logger import setup_logger, get_logger

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config(path: Path = None) -> dict[str, Any]:
    """Load and validate the YAML configuration file.

    Args:
        path: Path to the YAML config file.

    Returns:
        Parsed configuration dictionary.

    Raises:
        SystemExit: When the config file is missing or invalid.
    """
    if path is None:
        path = Path("/etc/secrets/config.yaml") if Path("/etc/secrets/config.yaml").exists() else CONFIG_PATH

    if not path.exists():
        print(f"❌ Configuration file not found: {path}")
        print("   Copy config.yaml.example → config.yaml and fill in your settings.")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)

    if not config:
        print("❌ Configuration file is empty.")
        sys.exit(1)

    return config


# ---------------------------------------------------------------------------
# Agent core
# ---------------------------------------------------------------------------

class ContentMonitorAgent:
    """Central agent that ties monitors, analyzer, storage, and notifiers.

    Lifecycle:
        1. Load config → create components.
        2. On each poll cycle, call :meth:`run_cycle`.
        3. Scheduler calls :meth:`run_cycle` on the configured interval.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.target_name: str = config.get("target", {}).get("name", "Unknown")

        # ---- Logging ----
        log_cfg = config.get("logging", {})
        setup_logger(
            "root",
            level=log_cfg.get("level", "INFO"),
            log_file=log_cfg.get("file"),
        )
        self.logger = get_logger("agent")

        # ---- Storage ----
        firebase_cred_path = config.get("firebase", {}).get("credential_path", "")
        self.storage = ContentStorage(firebase_cred_path=firebase_cred_path)

        # ---- AI Analyzer ----
        api_keys = config.get("api_keys", {})
        gemini_key = api_keys.get("gemini", "")
        if not gemini_key:
            self.logger.error("❌ Gemini API key is not configured. AI analysis will fail.")
        ai_cfg = config.get("ai", {})
        self.analyzer = ContentAnalyzer(
            api_key=gemini_key,
            model=ai_cfg.get("model", "gemini-2.5-flash"),
            temperature=ai_cfg.get("temperature", 0.3),
        )

        # ---- Platform Monitors ----
        self.monitors: list[tuple[str, Any]] = []
        self._init_monitors(config)

        # ---- Notifiers ----
        self.notifiers: list[tuple[str, Any]] = []
        self._init_notifiers(config)

        self.logger.info(
            "Agent initialized — target: %s, monitors: %d, notifiers: %d",
            self.target_name,
            len(self.monitors),
            len(self.notifiers),
        )

    # ------------------------------------------------------------------
    # Component initialization
    # ------------------------------------------------------------------

    def _init_monitors(self, config: dict[str, Any]) -> None:
        """Create enabled platform monitors."""
        platforms = config.get("platforms", {})
        target = config.get("target", {})
        api_keys = config.get("api_keys", {})
        ai_cfg = config.get("ai", {})

        if platforms.get("youtube") and target.get("youtube_channel_id"):
            yt = YouTubeMonitor(
                channel_id=target["youtube_channel_id"],
                api_key=api_keys.get("youtube_data_api") or None,
                analyze_transcripts=ai_cfg.get("analyze_transcripts", True),
                max_transcript_chars=ai_cfg.get("max_transcript_chars", 15000),
            )
            self.monitors.append(("youtube", yt))
            self.logger.info("✅ YouTube monitor enabled for channel %s", target["youtube_channel_id"])

        if platforms.get("instagram") and target.get("instagram_handle"):
            ig = InstagramMonitor(
                username=target["instagram_handle"],
                api_token=config.get("apify", {}).get("api_token", "")
            )
            self.monitors.append(("instagram", ig))
            self.logger.info("✅ Instagram monitor enabled for @%s", target["instagram_handle"])

        if platforms.get("twitter") and target.get("twitter_handle"):
            tw = TwitterMonitor(
                username=target["twitter_handle"],
                api_token=config.get("apify", {}).get("api_token", "")
            )
            self.monitors.append(("twitter", tw))
            self.logger.info("✅ Twitter monitor enabled for @%s", target["twitter_handle"])

        if not self.monitors:
            self.logger.warning(
                "⚠️  No monitors enabled! Check config.yaml — "
                "ensure platform flags are true and handles are filled in."
            )

    def _init_notifiers(self, config: dict[str, Any]) -> None:
        """Create enabled notification channels."""
        notif_flags = config.get("notifications", {})

        # Telegram
        if notif_flags.get("telegram"):
            tg_cfg = config.get("telegram", {})
            token = tg_cfg.get("bot_token", "")
            chat_id = tg_cfg.get("chat_id", "")
            if token and chat_id:
                tg = TelegramNotifier(bot_token=token, chat_id=chat_id)
                self.notifiers.append(("telegram", tg))
                self.logger.info("✅ Telegram notifier enabled")
            else:
                self.logger.warning("⚠️  Telegram enabled but bot_token or chat_id is empty")

        # Email
        if notif_flags.get("email"):
            em_cfg = config.get("email", {})
            required = ["smtp_server", "smtp_port", "sender_email", "sender_password", "recipient_email"]
            if all(em_cfg.get(k) for k in required):
                em = EmailNotifier(
                    smtp_server=em_cfg["smtp_server"],
                    smtp_port=em_cfg["smtp_port"],
                    sender_email=em_cfg["sender_email"],
                    sender_password=em_cfg["sender_password"],
                    recipient_email=em_cfg["recipient_email"],
                )
                self.notifiers.append(("email", em))
                self.logger.info("✅ Email notifier enabled")
            else:
                self.logger.warning("⚠️  Email enabled but required fields are missing")

        # Discord
        if notif_flags.get("discord"):
            dc_cfg = config.get("discord", {})
            webhook_url = dc_cfg.get("webhook_url", "")
            if webhook_url:
                dc = DiscordNotifier(webhook_url=webhook_url)
                self.notifiers.append(("discord", dc))
                self.logger.info("✅ Discord notifier enabled")
            else:
                self.logger.warning("⚠️  Discord enabled but webhook_url is empty")

        if not self.notifiers:
            self.logger.warning(
                "⚠️  No notifiers enabled! You won't receive any notifications."
            )

    # ------------------------------------------------------------------
    # Main polling cycle
    # ------------------------------------------------------------------

    def run_cycle(self) -> None:
        """Execute a single poll-analyze-notify cycle across all monitors."""
        self.logger.info("🔄 Starting poll cycle...")
        total_new = 0

        for platform_name, monitor in self.monitors:
            try:
                self.logger.info("📡 Checking %s...", platform_name)
                items = monitor.fetch_latest()
                self.logger.info("   Found %d items from %s", len(items), platform_name)

                for item in items:
                    content_id = item.get("content_id", "")
                    if not content_id:
                        continue

                    # Skip already-seen content.
                    if self.storage.is_seen(platform_name, content_id):
                        continue

                    self.logger.info(
                        "🆕 New content: [%s] %s", platform_name, item.get("title", "")[:60]
                    )

                    # Prepare content for analysis.
                    analysis_input = dict(item)
                    # Attach transcript if available (YouTube).
                    if "extra" in item and item["extra"].get("transcript"):
                        analysis_input["transcript"] = item["extra"]["transcript"]

                    # AI analysis.
                    analysis = self.analyzer.analyze(analysis_input)
                    self.logger.info(
                        "🤖 Analysis complete — importance: %s/10, category: %s",
                        analysis.get("importance_score", "?"),
                        analysis.get("content_category", "?"),
                    )

                    # Add target name to content for notification formatting.
                    item["target_name"] = self.target_name

                    # Send notifications.
                    for notif_name, notifier in self.notifiers:
                        try:
                            success = notifier.send(item, analysis)
                            if success:
                                self.logger.info("📬 Notification sent via %s", notif_name)
                            else:
                                self.logger.warning("⚠️  Notification failed via %s", notif_name)
                        except Exception as exc:
                            self.logger.error(
                                "❌ Notifier %s error: %s", notif_name, exc
                            )

                    if analysis.get("summary", "").startswith("Analysis failed"):
                        self.logger.warning("Analysis failed for %s, skipping to retry later.", item.get("title", ""))
                        continue

                    # Mark as seen and store full analysis for dashboard.
                    raw_data = {
                        **analysis,
                        "published_at": item.get("published_at", ""),
                        "thumbnail": item.get("thumbnail", ""),
                        "target_name": self.target_name,
                    }
                    self.storage.mark_seen(
                        platform=platform_name,
                        content_id=content_id,
                        url=item.get("url", ""),
                        title=item.get("title", ""),
                        content_type=item.get("content_type", ""),
                        summary=analysis.get("summary", ""),
                        raw_data=raw_data,
                    )
                    total_new += 1

            except Exception as exc:
                self.logger.error("❌ Error polling %s: %s", platform_name, exc)

        # Cycle summary.
        stats = self.storage.get_stats()
        self.logger.info(
            "✅ Poll cycle complete — %d new items found, %d total tracked",
            total_new,
            stats.get("total", 0),
        )

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    def send_startup_notifications(self) -> None:
        """Send a startup message through all enabled notifiers."""
        for notif_name, notifier in self.notifiers:
            try:
                if hasattr(notifier, "send_startup_message"):
                    notifier.send_startup_message()
                    self.logger.info("🚀 Startup message sent via %s", notif_name)
            except Exception as exc:
                self.logger.warning("Could not send startup message via %s: %s", notif_name, exc)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Load configuration, initialize the agent, and start polling."""
    print()
    print("=" * 60)
    print("  🤖 Content Monitor Agent")
    print("  Monitoring social media for new content")
    print("=" * 60)
    print()

    # Load config.
    config = load_config()
    interval = config.get("polling_interval", 5)

    # Change working directory to project root so relative paths work.
    os.chdir(Path(__file__).parent)

    # Create agent.
    agent = ContentMonitorAgent(config)

    # Send startup notifications.
    agent.send_startup_notifications()

    # Run first cycle immediately.
    print(f"\n🚀 Running initial scan...\n")
    agent.run_cycle()

    # Schedule recurring cycles.
    print(f"\n⏰ Scheduling polls every {interval} minutes...\n")
    print("Press Ctrl+C to stop.\n")

    scheduler = BlockingScheduler()
    scheduler.add_job(
        agent.run_cycle,
        "interval",
        minutes=interval,
        id="content_poll",
        name=f"Poll every {interval} min",
        max_instances=1,
        coalesce=True,
    )

    # Graceful shutdown on Ctrl+C.
    def shutdown(signum: int, frame: Any) -> None:
        print("\n\n🛑 Shutting down Content Monitor Agent...")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\n🛑 Agent stopped.")


if __name__ == "__main__":
    main()
