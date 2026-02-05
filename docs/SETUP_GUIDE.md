# II-Telegram-Agent Complete Setup Guide

This guide will walk you through setting up II-Telegram-Agent on your own hardware - from a Raspberry Pi to a dedicated server.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Getting Your API Keys](#getting-your-api-keys)
3. [Installation Options](#installation-options)
4. [Configuration](#configuration)
5. [Running the Bot](#running-the-bot)
6. [Security Setup](#security-setup)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Hardware Requirements

| Device | RAM | Storage | Notes |
|--------|-----|---------|-------|
| Raspberry Pi 5 | 8GB | 32GB+ SD | Works great |
| Intel NUC | 8GB+ | 64GB+ SSD | Recommended |
| Mini PC | 8GB+ | 64GB+ | Any x86_64 |
| Cloud VM | 2GB+ | 20GB+ | AWS/GCP/Azure |

### Software Requirements

- **Operating System**: Ubuntu 22.04+, Debian 12+, or Raspberry Pi OS
- **Docker**: 24.0+ (recommended) OR Python 3.10+
- **Internet Connection**: Required for Telegram and LLM APIs

---

## Getting Your API Keys

### 1. Telegram Bot Token (Required)

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Give your bot a name (e.g., "My AI Assistant")
4. Give your bot a username (must end in `bot`, e.g., `my_ai_assistant_bot`)
5. Copy the API token (looks like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. LLM API Key (Required - choose at least one)

#### Option A: Anthropic Claude (Recommended)
1. Go to [console.anthropic.com](https://console.anthropic.com/)
2. Create an account or sign in
3. Navigate to API Keys
4. Create a new API key
5. Copy and save it securely

#### Option B: OpenAI
1. Go to [platform.openai.com](https://platform.openai.com/)
2. Create an account or sign in
3. Navigate to API Keys
4. Create a new secret key
5. Copy and save it securely

#### Option C: Google AI (Gemini)
1. Go to [makersuite.google.com](https://makersuite.google.com/)
2. Sign in with your Google account
3. Click "Get API Key"
4. Copy and save it securely

#### Option D: OpenRouter (Access multiple models)
1. Go to [openrouter.ai](https://openrouter.ai/)
2. Create an account
3. Navigate to Keys
4. Create a new API key
5. Copy and save it securely

### 3. Optional API Keys

#### Tavily (Better Web Search)
1. Go to [tavily.com](https://tavily.com/)
2. Sign up for a free account
3. Get your API key from the dashboard

#### E2B (Code Execution Sandboxes)
1. Go to [e2b.dev](https://e2b.dev/)
2. Create an account
3. Get your API key from settings

---

## Installation Options

### Option 1: Docker (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/Jack-Batman/ii-telegram-agent.git
cd ii-telegram-agent

# 2. Create your configuration
cp .env.example .env

# 3. Edit with your API keys
nano .env

# 4. Start the bot
docker compose up -d

# 5. View logs
docker compose logs -f
```

### Option 2: Direct Python Installation

```bash
# 1. Clone the repository
git clone https://github.com/Jack-Batman/ii-telegram-agent.git
cd ii-telegram-agent

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install
pip install -e .

# 4. Initialize
ii-telegram init

# 5. Edit configuration
nano .env

# 6. Start the bot
ii-telegram serve
```

### Option 3: Small PC Setup Script

```bash
# Download and run the setup script
curl -fsSL https://raw.githubusercontent.com/Jack-Batman/ii-telegram-agent/main/scripts/setup-small-pc.sh | bash
```

---

## Configuration

### Essential Settings (.env file)

```bash
# === REQUIRED ===

# Your Telegram bot token from @BotFather
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz

# At least one LLM API key
ANTHROPIC_API_KEY=sk-ant-...

# === RECOMMENDED ===

# Better web search
TAVILY_API_KEY=tvly-...

# Admin password (change this!)
ADMIN_PASSWORD=your-secure-password

# === OPTIONAL ===

# Restrict to specific Telegram users (comma-separated IDs)
ALLOWED_USERS=123456789,987654321

# Disable pairing (not recommended for public bots)
PAIRING_ENABLED=true
```

### Model Configuration

You can change the default AI model:

```bash
# Use Claude Opus (more capable, slower)
DEFAULT_MODEL=claude-opus-4-20250514

# Use GPT-4o
DEFAULT_PROVIDER=openai
DEFAULT_MODEL=gpt-4o

# Use Gemini
DEFAULT_PROVIDER=google
DEFAULT_MODEL=gemini-2.0-flash
```

---

## Running the Bot

### Starting

```bash
# With Docker
docker compose up -d

# Without Docker
ii-telegram serve
```

### Stopping

```bash
# With Docker
docker compose down

# Without Docker
Ctrl+C
```

### Viewing Logs

```bash
# With Docker
docker compose logs -f

# Without Docker (logs are printed to console)
```

### Auto-Start on Boot

```bash
# Enable systemd service
sudo systemctl enable ii-telegram-agent
sudo systemctl start ii-telegram-agent
```

---

## Security Setup

### 1. Pairing Mode (Default)

New users receive a pairing code that must be approved:

```bash
# User sends message to bot, gets code like "ABC123"
# Admin approves via CLI:
ii-telegram pair approve ABC123

# Or via API:
curl -X POST http://localhost:8080/api/pair/approve \
  -H "Authorization: Bearer your-admin-password" \
  -H "Content-Type: application/json" \
  -d '{"code": "ABC123"}'
```

### 2. Allowlist Mode

Restrict to specific Telegram user IDs:

```bash
# In .env file:
ALLOWED_USERS=123456789,987654321

# Find your Telegram ID by messaging @userinfobot
```

### 3. Rate Limiting

Prevent abuse by limiting messages per minute:

```bash
# In .env file (default: 30 messages/minute):
RATE_LIMIT_MESSAGES=30
```

### 4. Webhook Mode (for public deployments)

For production, use webhooks instead of polling:

```bash
# In .env file:
TELEGRAM_WEBHOOK_URL=https://your-domain.com/webhook/telegram
TELEGRAM_WEBHOOK_SECRET=random-secure-string
```

---

## Troubleshooting

### Bot Doesn't Respond

1. Check if the bot is running:
   ```bash
   docker compose ps  # or check process
   ```

2. Check logs for errors:
   ```bash
   docker compose logs -f
   ```

3. Verify your API tokens:
   ```bash
   ii-telegram config --check
   ```

### "API Key Invalid" Error

- Ensure the API key is correctly copied (no extra spaces)
- Check that your API key has credits/quota
- Try regenerating the key

### "Rate Limited" Messages

- You're sending too many messages too quickly
- Wait a minute and try again
- Increase `RATE_LIMIT_MESSAGES` if needed

### Database Errors

```bash
# Reset the database (WARNING: deletes all data)
rm -rf data/agent.db
ii-telegram serve
```

### Docker Permission Issues

```bash
# Add your user to docker group
sudo usermod -aG docker $USER
# Log out and back in
```

### Memory Issues on Raspberry Pi

- Use a model with smaller context (gpt-4o-mini instead of gpt-4o)
- Reduce `MAX_CONTEXT_MESSAGES` to 20

---

## Next Steps

1. **Customize the system prompt**: Edit the `DEFAULT_SYSTEM_PROMPT` in `src/ii_telegram_agent/agent/core.py`

2. **Add custom tools**: Create new tools in `src/ii_telegram_agent/tools/`

3. **Set up monitoring**: Use the `/api/stats` endpoint for usage tracking

4. **Enable remote access**: Set up Tailscale or a reverse proxy

---

## Getting Help

- Check the [GitHub Issues](https://github.com/Jack-Batman/ii-telegram-agent/issues)
- Read the [Architecture docs](./architecture.md)
- Join the community Discord (coming soon)

---

## License

MIT License - Free to use, modify, and distribute.