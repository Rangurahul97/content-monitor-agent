# 🤖 Content Monitor Agent

A powerful AI-powered automation agent that monitors a specific person's social media activity across **YouTube**, **Instagram**, and **Twitter/X** — automatically analyzing every new post with Google's **Gemini AI** and sending you beautifully formatted notifications.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📺 **YouTube Monitoring** | Detects new videos & Shorts via RSS feed (no API key required) |
| 📸 **Instagram Monitoring** | Tracks new posts & reels via RapidAPI or RSS bridge |
| 🐦 **Twitter/X Monitoring** | Monitors tweets & threads via RSS bridge fallbacks |
| 🤖 **AI Analysis** | Deep content analysis using Gemini 2.5 Flash (free tier) |
| 📝 **Smart Summaries** | Auto-generates summaries, key topics, takeaways, and importance scores |
| 📺 **Transcript Analysis** | Analyzes full YouTube video transcripts for deep insights |
| 📬 **Multi-Channel Notifications** | Telegram, Email, and Discord support |
| 💾 **Deduplication** | SQLite database prevents duplicate notifications |
| 🔄 **Configurable Polling** | Set check frequency from 1 minute to hours |
| 📊 **Beautiful Formatting** | Rich emoji-formatted notifications with all key details |

---

## 🚀 Quick Start

### 1. Prerequisites

- **Python 3.10+** installed ([Download](https://python.org/downloads))
- **Gemini API Key** (free) — [Get one here](https://aistudio.google.com)
- **Telegram Bot** (free, 2 minutes) — See setup below

### 2. Install Dependencies

```bash
cd content-monitor-agent
pip install -r requirements.txt
```

### 3. Configure

Edit `config.yaml` with your settings:

```yaml
# Who to monitor
target:
  name: "Creator Name"
  youtube_channel_id: "UCxxxxxxxxxxxxxxxxxx"  # Required
  instagram_handle: "username"                 # Optional
  twitter_handle: "username"                   # Optional

# Your API keys
api_keys:
  gemini: "your-gemini-api-key-here"

# Your Telegram bot
telegram:
  bot_token: "123456:ABC-DEF1234..."
  chat_id: "your-chat-id"
```

### 4. Run

```bash
python main.py
```

That's it! The agent will:
1. ✅ Run an initial scan immediately
2. ⏰ Poll for new content every 5 minutes (configurable)
3. 🤖 Analyze any new content with Gemini AI
4. 📬 Send you a notification with the analysis

---

## 📱 Setting Up Notifications

### Telegram Bot (Recommended — Free & Instant)

1. **Create a bot**: Open Telegram, search for `@BotFather`, send `/newbot`
2. **Get the token**: BotFather will give you a token like `123456:ABC-DEF1234...`
3. **Get your chat ID**:
   - Send any message to your new bot
   - Visit: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   - Find your `chat_id` in the response JSON
4. **Fill in** `config.yaml`:
   ```yaml
   telegram:
     bot_token: "your-token-here"
     chat_id: "your-chat-id-here"
   ```

### Email (Gmail)

1. Enable [2-Factor Authentication](https://myaccount.google.com/security) on your Google account
2. Create an [App Password](https://myaccount.google.com/apppasswords)
3. Fill in `config.yaml`:
   ```yaml
   email:
     smtp_server: "smtp.gmail.com"
     smtp_port: 587
     sender_email: "your-email@gmail.com"
     sender_password: "your-app-password"
     recipient_email: "your-email@gmail.com"
   notifications:
     email: true
   ```

### Discord Webhook

1. In your Discord server: **Server Settings → Integrations → Webhooks → New Webhook**
2. Copy the webhook URL
3. Fill in `config.yaml`:
   ```yaml
   discord:
     webhook_url: "https://discord.com/api/webhooks/..."
   notifications:
     discord: true
   ```

---

## 🔍 Finding YouTube Channel IDs

1. Go to the YouTube channel page
2. **Method 1**: View page source (Ctrl+U) and search for `channelId`
3. **Method 2**: Use [YouTube Channel ID Finder](https://commentpicker.com/youtube-channel-id.php)
4. The ID looks like: `UCxxxxxxxxxxxxxxxxxx` (starts with `UC`)

---

## 📋 Sample Notification

Here's what a Telegram notification looks like:

```
🔔 NEW YOUTUBE VIDEO

📺 How I Built an AI Agent in 10 Minutes
👤 Creator Name
📅 2025-07-08T12:30:00+00:00

📋 Summary:
The creator demonstrates building a custom AI agent
using Python and the Gemini API, covering setup,
prompt engineering, and deployment steps.

🎯 Key Topics:
  • AI Agent Development
  • Gemini API Integration
  • Python Automation

💡 Key Takeaways:
  • Use structured prompts for reliable output
  • Free tier is sufficient for personal agents
  • Can be deployed in under 10 minutes

📊 Category: tutorial
🔥 Importance: 8/10 🔥🔥🔥🔥🔥🔥🔥🔥
💭 Sentiment: positive

🔗 View Original
```

---

## ⚙️ Configuration Reference

### Platforms

| Setting | Description | Default |
|---------|-------------|---------|
| `platforms.youtube` | Enable YouTube monitoring | `true` |
| `platforms.instagram` | Enable Instagram monitoring | `false` |
| `platforms.twitter` | Enable Twitter/X monitoring | `true` |

### AI Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `ai.model` | Gemini model to use | `gemini-2.5-flash` |
| `ai.temperature` | Analysis creativity (0-1) | `0.3` |
| `ai.analyze_transcripts` | Analyze full YouTube transcripts | `true` |
| `ai.max_transcript_chars` | Max transcript length | `15000` |

### Polling

| Setting | Description | Default |
|---------|-------------|---------|
| `polling_interval` | Minutes between checks | `5` |

---

## 🏗️ Project Structure

```
content-monitor-agent/
├── config.yaml              # ← Your settings go here
├── main.py                  # Entry point & scheduler
├── requirements.txt         # Python dependencies
├── monitors/
│   ├── youtube.py           # YouTube RSS feed monitor
│   ├── instagram.py         # Instagram monitor (RapidAPI/RSS)
│   └── twitter.py           # Twitter/X monitor (RSS bridges)
├── analyzer/
│   └── ai_engine.py         # Gemini AI analysis engine
├── notifiers/
│   ├── telegram.py          # Telegram Bot API notifications
│   ├── email_notify.py      # Email (SMTP) notifications
│   └── discord.py           # Discord webhook notifications
├── database/
│   └── storage.py           # SQLite deduplication storage
├── utils/
│   └── logger.py            # Colored console logging
└── data/
    └── content_history.db   # Auto-created SQLite database
```

---

## 🔧 Troubleshooting

### "No monitors enabled"
→ Make sure `config.yaml` has platform flags set to `true` AND the corresponding handles are filled in.

### "Gemini API key is not configured"
→ Get a free key from [aistudio.google.com](https://aistudio.google.com) and add it to `config.yaml`.

### YouTube RSS not working
→ Double-check the channel ID. It should start with `UC` and be exactly 24 characters.

### Instagram not returning results
→ Instagram scraping is unreliable without a RapidAPI key. Get a free key from [RapidAPI](https://rapidapi.com/hub) and search for "Instagram Scraper".

### Telegram not sending messages
→ Make sure you've sent at least one message to your bot first, then get the chat ID from the getUpdates API endpoint.

---

## 💰 Cost

**Everything is free!**

| Service | Free Tier |
|---------|-----------|
| Gemini 2.5 Flash | 15 RPM, 1M tokens/day |
| Telegram Bot API | Unlimited |
| YouTube RSS | Unlimited |
| SQLite | Local, no limits |

---

## 📄 License

This project is free for personal use. Built with ❤️ by your AI assistant.
