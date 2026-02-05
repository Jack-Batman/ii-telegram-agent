# 🤖 II-Telegram-Agent

**Your personal AI assistant on Telegram, with a soul and memory**

Run your own AI assistant that you can chat with via Telegram. It combines the best features of [OpenClaw](https://github.com/openclaw/openclaw)'s personality system with [II-Agent](https://github.com/Intelligent-Internet/ii-agent)'s powerful AI capabilities.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)

## ✨ Features

### 🧠 Soul & Memory System (Like OpenClaw)
- 🎭 **Customizable Personality**: Define your assistant's communication style
- 📝 **Long-Term Memory**: Remembers important information across conversations
- 👤 **User Profile**: Knows who you are and your preferences
- 🔄 **Persistent Context**: Never forgets what you've discussed

### From OpenClaw
- 🔐 **Security First**: User allowlists, pairing codes, rate limiting
- 💬 **Telegram Integration**: Full webhook and polling support
- 🔄 **Session Management**: Persistent conversations with context
- 🎯 **Per-User Settings**: Custom models and preferences

### From II-Agent
- 🧠 **Multi-Model Support**: Claude, GPT-4, Gemini, and more
- 🔍 **Web Search**: Find current information online
- 🌐 **Browser Tool**: Read and extract content from web pages
- 🐍 **Code Execution**: Run Python code in sandboxes
- 📊 **Deep Research**: Comprehensive information gathering

### Unique Features
- 🏠 **Self-Hosted**: Runs entirely on your hardware
- 🖥️ **Small PC Ready**: Optimized for Intel NUCs, mini PCs, Raspberry Pi 5
- 🐳 **Docker Support**: Easy deployment with Docker Compose
- 🔌 **API Keys**: Bring your own LLM API keys
- 📈 **Usage Tracking**: Monitor your AI usage

## 🚀 One-Line Installation

The easiest way to get started - just run this command and follow the interactive wizard:

```bash
curl -fsSL https://raw.githubusercontent.com/Jack-Batman/ii-telegram-agent/main/install.sh | bash
```

The installer will:
1. ✅ Check and install dependencies
2. 🤖 Guide you through creating a Telegram bot
3. 🔑 Set up your AI provider (Claude, GPT, Gemini, or OpenRouter)
4. 👤 Create your user profile
5. 🎭 Customize your assistant's personality
6. 🚀 Start your bot automatically

**No .env file editing required!**

---

## 📦 Alternative Installation Methods

### Option 1: Docker (For Experienced Users)

```bash
# Clone the repository
git clone https://github.com/Jack-Batman/ii-telegram-agent.git
cd ii-telegram-agent

# Run the interactive installer
./install.sh

# Or manually with Docker Compose
cp .env.example .env
nano .env  # Add your tokens and API keys
docker-compose up -d
```

### Option 2: Manual Installation

```bash
# Clone the repository
git clone https://github.com/Jack-Batman/ii-telegram-agent.git
cd ii-telegram-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -e .

# Run the interactive setup
./install.sh

# Or initialize manually
ii-telegram init
nano .env  # Add your tokens
ii-telegram serve
```

---

## 🎭 Soul & Memory System

What makes this bot special is its **soul and memory** - just like OpenClaw!

### Configuration Files

After installation, you'll find these files in your workspace:

| File | Purpose |
|------|---------||
| `SOUL.md` | Your assistant's personality, communication style, and values |
| `USER.md` | Information about you - name, timezone, goals, preferences |
| `MEMORY.md` | Long-term memory that persists across conversations |
| `AGENTS.md` | Tool capabilities and configuration |

### Customizing Your Assistant

**Edit `SOUL.md`** to change how your assistant communicates:

```markdown
## Personality
My core traits are: witty, insightful, always ready with a clever observation

## Communication Style
- I use humor to make complex topics accessible
- I'm direct but never rude
- I occasionally reference pop culture when relevant
```

**Edit `USER.md`** to help your assistant know you:

```markdown
## Identity
- **Name**: Alex
- **Timezone**: America/New_York

## Goals & Priorities
Building a startup, learning machine learning, staying healthy
```

Your assistant will automatically use this context in conversations!

## 📱 Using Your Bot

1. **Start a chat** with your bot on Telegram
2. **Send `/start`** to initialize
3. If pairing is enabled, you'll get a code to approve

### Commands

| Command | Description |
|---------|-------------|
| `/start` | Initialize or restart the bot |
| `/help` | Show help message |
| `/clear` | Clear conversation history |
| `/model [name]` | View or change AI model |
| `/status` | Show system status |
| `/remember [text]` | Save something to memory |
| `/forget` | Clear conversation (keeps long-term memory) |
| `/soul` | Show current personality settings |

### Approving Users

When pairing is enabled, new users get a code:

```bash
# Approve via CLI
ii-telegram pair approve ABC123

# Or via API
curl -X POST http://localhost:8080/api/pair/approve \
  -H "Authorization: Bearer your-admin-password" \
  -H "Content-Type: application/json" \
  -d '{"code": "ABC123"}'
```

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------||
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (required) | - |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `DEFAULT_PROVIDER` | LLM provider | `anthropic` |
| `DEFAULT_MODEL` | Default model | `claude-sonnet-4-20250514` |
| `PAIRING_ENABLED` | Require approval for new users | `true` |
| `ALLOWED_USERS` | Comma-separated allowed IDs | - |
| `TAVILY_API_KEY` | Web search API key | - |

See `.env.example` for all options.

### Webhook vs Polling

**Polling Mode** (default):
- Works behind NAT/firewalls
- No public URL needed
- Slightly higher latency

**Webhook Mode**:
- Faster response times
- Requires public HTTPS URL
- Set `TELEGRAM_WEBHOOK_URL` in `.env`

## 🏠 Deployment on Small PC

### Recommended Hardware

- **Intel NUC** or mini PC with 8GB+ RAM
- **Raspberry Pi 5** (8GB model)
- Any x86_64 or ARM64 system with Docker

### Setup Steps

1. Install Docker and Docker Compose
2. Clone this repository
3. Configure `.env`
4. Run `docker-compose up -d`
5. (Optional) Set up Tailscale for remote access
6. (Optional) Configure systemd for auto-start

### Example: Running on Raspberry Pi 5

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Clone and configure
git clone https://github.com/Jack-Batman/ii-telegram-agent.git
cd ii-telegram-agent
cp .env.example .env
nano .env

# Start
docker-compose up -d
```

## 🔌 API Reference

### Health Check
```
GET /api/health
```

### Statistics
```
GET /api/stats
```

### Webhook (for Telegram)
```
POST /webhook/telegram
```

### User Management
```
GET /api/users
Authorization: Bearer <admin-password>
```

### Approve Pairing
```
POST /api/pair/approve
Authorization: Bearer <admin-password>
{"code": "ABC123"}
```

## 🛠️ Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check src/

# Type checking
mypy src/
```

## 📊 Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│  Telegram   │────▶│   Gateway   │────▶│   Agent Core    │
│   Users     │     │   (FastAPI) │     │  (LLM + Tools)  │
└─────────────┘     └─────────────┘     └─────────────────┘
                           │                     │
                           ▼                     ▼
                    ┌─────────────┐     ┌─────────────────┐
                    │  Database   │     │     Tools       │
                    │  (SQLite/   │     │  - Web Search   │
                    │   Postgres) │     │  - Browser      │
                    └─────────────┘     │  - Code Exec    │
                                        │  - Remember     │
                                        │  - Recall       │
                                        └─────────────────┘
                                               │
                                               ▼
                                        ┌─────────────────┐
                                        │  Workspace      │
                                        │  - SOUL.md      │
                                        │  - USER.md      │
                                        │  - MEMORY.md    │
                                        └─────────────────┘
```

### How Memory Works

1. **SOUL.md** → Loaded at startup to define the system prompt
2. **USER.md** → Added to context so the assistant knows who you are
3. **MEMORY.md** → Searched and updated during conversations
4. **Remember Tool** → AI can save important information
5. **Recall Tool** → AI can search through saved memories

## 🔒 Security

- **Allowlist Mode**: Only approved users can interact
- **Pairing Mode**: New users get a code, admin approves
- **Rate Limiting**: Prevent abuse
- **Webhook Secret**: Verify Telegram updates
- **Admin Password**: Protect API endpoints

## 📝 License

MIT License - see [LICENSE](LICENSE)

## 🙏 Credits

- [OpenClaw](https://github.com/openclaw/openclaw) - Gateway design inspiration
- [II-Agent](https://github.com/Intelligent-Internet/ii-agent) - AI agent capabilities
- [python-telegram-bot](https://python-telegram-bot.org/) - Telegram integration
- [FastAPI](https://fastapi.tiangolo.com/) - API framework

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request