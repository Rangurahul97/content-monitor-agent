"""Email notification module using SMTP.

Sends styled HTML emails containing content analysis results with a
dark-themed design and per-platform accent colors.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)


class EmailNotifier:
    """Sends HTML-formatted content analysis emails via SMTP.

    Emails use inline CSS with a dark theme and platform-specific accent
    colours for a visually appealing reading experience.

    Attributes:
        smtp_server: SMTP server hostname.
        smtp_port: SMTP server port (usually 587 for STARTTLS).
        sender_email: Email address used as the sender.
        sender_password: Password or app-password for SMTP authentication.
        recipient_email: Destination email address.
    """

    _PLATFORM_COLORS: dict[str, str] = {
        "youtube": "#FF0000",
        "instagram": "#E1306C",
        "twitter": "#1DA1F2",
    }

    _PLATFORM_EMOJIS: dict[str, str] = {
        "youtube": "📺",
        "instagram": "📸",
        "twitter": "🐦",
    }

    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        sender_email: str,
        sender_password: str,
        recipient_email: str,
    ) -> None:
        """Initialize the email notifier.

        Args:
            smtp_server: SMTP server hostname (e.g. ``smtp.gmail.com``).
            smtp_port: SMTP port (e.g. ``587`` for STARTTLS).
            sender_email: Sender's email address.
            sender_password: Sender's password or app-specific password.
            recipient_email: Recipient's email address.
        """
        self.smtp_server: str = smtp_server
        self.smtp_port: int = smtp_port
        self.sender_email: str = sender_email
        self.sender_password: str = sender_password
        self.recipient_email: str = recipient_email
        logger.info(
            "EmailNotifier initialized: %s -> %s via %s:%d",
            sender_email,
            recipient_email,
            smtp_server,
            smtp_port,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send(self, content: dict[str, Any], analysis: dict[str, Any]) -> bool:
        """Send a styled HTML email with the content analysis.

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
            ``True`` if the email was sent successfully, ``False`` otherwise.
        """
        platform: str = content.get("platform", "unknown")
        content_type: str = content.get("content_type", "content")
        title: str = content.get("title", "Untitled")

        subject = f"🔔 New {platform.capitalize()} {content_type}: {title}"
        html_body = self._build_html(content, analysis)

        return self._send_email(subject, html_body)

    # ------------------------------------------------------------------
    # HTML construction
    # ------------------------------------------------------------------

    def _build_html(
        self,
        content: dict[str, Any],
        analysis: dict[str, Any],
    ) -> str:
        """Build a complete HTML email body with inline CSS.

        Args:
            content: Content metadata dictionary.
            analysis: Analysis result dictionary.

        Returns:
            A full HTML document string suitable for email delivery.
        """
        platform: str = content.get("platform", "unknown").lower()
        content_type: str = content.get("content_type", "content")
        title: str = self._esc(content.get("title", "Untitled"))
        url: str = content.get("url", "#")
        published_at: str = self._esc(content.get("published_at", "N/A"))
        target_name: str = self._esc(content.get("target_name", "Unknown"))

        accent: str = self._PLATFORM_COLORS.get(platform, "#6C63FF")
        platform_emoji: str = self._PLATFORM_EMOJIS.get(platform, "📌")

        summary: str = self._esc(analysis.get("summary", "N/A"))
        key_topics: list[str] = analysis.get("key_topics", [])
        key_takeaways: list[str] = analysis.get("key_takeaways", [])
        content_category: str = self._esc(
            analysis.get("content_category", "N/A")
        )
        importance_score: int = analysis.get("importance_score", 5)
        sentiment: str = self._esc(analysis.get("sentiment", "neutral"))

        topics_html = "".join(
            f"<li>{self._esc(t)}</li>" for t in key_topics
        ) or "<li>N/A</li>"

        takeaways_html = "".join(
            f"<li>{self._esc(t)}</li>" for t in key_takeaways
        ) or "<li>N/A</li>"

        importance_bar = self._render_importance_bar(importance_score, accent)

        return f"""\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background-color:#0f0f1a;font-family:
  'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" role="presentation"
       style="background-color:#0f0f1a;padding:24px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0"
       style="background-color:#1a1a2e;border-radius:12px;overflow:hidden;">

  <!-- Header -->
  <tr>
    <td style="background-color:{accent};padding:20px 24px;">
      <h1 style="margin:0;color:#ffffff;font-size:20px;">
        🔔 New {self._esc(platform.capitalize())} {self._esc(content_type.capitalize())}
      </h1>
    </td>
  </tr>

  <!-- Title & meta -->
  <tr>
    <td style="padding:24px;">
      <h2 style="margin:0 0 8px;color:#ffffff;font-size:18px;">
        {platform_emoji} {title}
      </h2>
      <p style="margin:0 0 4px;color:#a0a0b8;font-size:13px;">
        👤 {target_name} &nbsp;|&nbsp; 📅 {published_at}
      </p>
    </td>
  </tr>

  <!-- Summary -->
  <tr>
    <td style="padding:0 24px 16px;">
      <h3 style="margin:0 0 8px;color:{accent};font-size:14px;
          text-transform:uppercase;letter-spacing:1px;">📋 Summary</h3>
      <p style="margin:0;color:#d0d0e0;font-size:14px;line-height:1.6;">
        {summary}
      </p>
    </td>
  </tr>

  <!-- Key Topics -->
  <tr>
    <td style="padding:0 24px 16px;">
      <h3 style="margin:0 0 8px;color:{accent};font-size:14px;
          text-transform:uppercase;letter-spacing:1px;">🎯 Key Topics</h3>
      <ul style="margin:0;padding-left:20px;color:#d0d0e0;font-size:14px;
          line-height:1.8;">
        {topics_html}
      </ul>
    </td>
  </tr>

  <!-- Key Takeaways -->
  <tr>
    <td style="padding:0 24px 16px;">
      <h3 style="margin:0 0 8px;color:{accent};font-size:14px;
          text-transform:uppercase;letter-spacing:1px;">💡 Key Takeaways</h3>
      <ul style="margin:0;padding-left:20px;color:#d0d0e0;font-size:14px;
          line-height:1.8;">
        {takeaways_html}
      </ul>
    </td>
  </tr>

  <!-- Scores -->
  <tr>
    <td style="padding:0 24px 16px;">
      <table width="100%" cellpadding="8" cellspacing="0"
             style="background-color:#16213e;border-radius:8px;">
        <tr>
          <td style="color:#a0a0b8;font-size:13px;width:33%;
              text-align:center;border-right:1px solid #1a1a2e;">
            📊 <b style="color:#ffffff;">Category</b><br>{content_category}
          </td>
          <td style="color:#a0a0b8;font-size:13px;width:34%;
              text-align:center;border-right:1px solid #1a1a2e;">
            🔥 <b style="color:#ffffff;">Importance</b><br>
            {importance_score}/10<br>{importance_bar}
          </td>
          <td style="color:#a0a0b8;font-size:13px;width:33%;
              text-align:center;">
            💭 <b style="color:#ffffff;">Sentiment</b><br>{sentiment}
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- CTA -->
  <tr>
    <td style="padding:8px 24px 24px;text-align:center;">
      <a href="{url}" style="display:inline-block;padding:12px 32px;
         background-color:{accent};color:#ffffff;text-decoration:none;
         border-radius:6px;font-weight:bold;font-size:14px;">
        🔗 View Original
      </a>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>"""

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def _send_email(self, subject: str, html_body: str) -> bool:
        """Send an email via SMTP with STARTTLS.

        Args:
            subject: Email subject line.
            html_body: Complete HTML body string.

        Returns:
            ``True`` on success, ``False`` on failure.
        """
        msg = MIMEMultipart("alternative")
        msg["From"] = self.sender_email
        msg["To"] = self.recipient_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.sender_email, self.sender_password)
                server.sendmail(
                    self.sender_email,
                    self.recipient_email,
                    msg.as_string(),
                )
            logger.info("Email sent successfully to %s", self.recipient_email)
            return True

        except smtplib.SMTPException:
            logger.exception(
                "SMTP error sending email to %s", self.recipient_email
            )
            return False
        except OSError:
            logger.exception(
                "Network error connecting to %s:%d",
                self.smtp_server,
                self.smtp_port,
            )
            return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _esc(text: str) -> str:
        """Escape HTML special characters.

        Args:
            text: Raw string.

        Returns:
            HTML-safe string.
        """
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    @staticmethod
    def _render_importance_bar(score: int, accent: str) -> str:
        """Render a small inline HTML bar for the importance score.

        Args:
            score: Importance score (1–10).
            accent: Hex colour for the filled portion.

        Returns:
            HTML string representing a visual bar.
        """
        pct = max(0, min(100, score * 10))
        return (
            f'<div style="background-color:#0f0f1a;border-radius:4px;'
            f'height:6px;width:100%;margin-top:4px;">'
            f'<div style="background-color:{accent};border-radius:4px;'
            f'height:6px;width:{pct}%;"></div></div>'
        )
