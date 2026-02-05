# 🤖 II-Telegram-Agent

**Your personal AI assistant on Telegram, powered by II-Agent technology**

Run your own AI assistant that you can chat with via Telegram. It combines the best features of [OpenClaw](https://github.com/openclaw/openclaw)'s gateway design with [II-Agent](https://github.com/Intelligent-Internet/ii-agent)'s powerful AI capabilities.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)

## ✨ Features

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

## 🚀 Quick Start

### Prerequisites

- Python 3.10+ (or Docker)
- A Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- At least one LLM API key (Anthropic, OpenAI, or Google)

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/Jack-Batman/ii-telegram-agent.git
cd ii-telegram-agent

# Copy and edit the environment file
cp .env.example .env
nano .env  # Add your tokens and API keys

# Start with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f
```

### Option 2: Local Installation

```bash
# Clone the repository
git clone https://github.com/Jack-Batman/ii-telegram-agent.git
cd ii-telegram-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -e .

# Initialize (creates .env and data directory)
ii-telegram init

# Edit .env with your tokens
nano .env

# Start the bot
ii-telegram serve
```

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
|----------|-------------|----------|
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
                                        └─────────────────┘
```

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