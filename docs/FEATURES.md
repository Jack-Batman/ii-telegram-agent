# Features Deep Dive

## Architecture Overview

II-Telegram-Agent combines the best of two worlds:

- **OpenClaw's** soul/memory personality system, heartbeat proactivity, exec-approval security, and multi-channel architecture
- **II-Agent's** powerful multi-model LLM support, deep research tools, code execution, and extensible tool system

```
                    ┌──────────────────────────────────────────┐
                    │              Channel Layer                │
                    │  ┌──────────┐ ┌─────────┐ ┌──────────┐  │
                    │  │ Telegram │ │ Discord │ │ WhatsApp │  │
                    │  └────┬─────┘ └────┬────┘ └────┬─────┘  │
                    │       └───────┬────┘           │         │
                    └───────────────┼────────────────┘         │
                                    ▼                          │
┌──────────────┐    ┌──────────────────────────────┐          │
│  SOUL.md     │───▶│         Agent Core            │◀─────────┘
│  USER.md     │    │  ┌─────────────────────┐     │
│  MEMORY.md   │───▶│  │ Conversation Engine │     │
└──────────────┘    │  │ + Compaction        │     │
                    │  └─────────┬───────────┘     │
                    │            │                  │
                    │  ┌─────────▼───────────┐     │
                    │  │   LLM Router        │     │
                    │  │  Claude│GPT│Gemini   │     │
                    │  └─────────┬───────────┘     │
                    │            │                  │
                    │  ┌─────────▼───────────┐     │
                    │  │   Tool Registry     │     │
                    │  │  + Exec Approval    │     │
                    │  └─────────────────────┘     │
                    └──────────────────────────────┘
                                │
        ┌───────────┬───────────┼───────────┬───────────┐
        ▼           ▼           ▼           ▼           ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
   │Web Search│ │ Browser │ │  Code   │ │  Shell  │ │  Email  │
   │ +Tavily │ │+Crawling│ │  Exec   │ │ +Approve│ │+Calendar│
   └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘
```

## From OpenClaw

### Soul & Memory System
- **SOUL.md**: Defines personality, communication style, values, and boundaries
- **USER.md**: Stores user profile info (name, timezone, goals, preferences)
- **MEMORY.md**: Long-term memory that persists across conversations
- **AGENTS.md**: Tool capabilities and configuration

### Heartbeat Proactive System
- Periodic check-ins during configurable active hours
- Monitors inbox, calendar, and custom triggers
- Sends proactive messages via Telegram when tasks fire
- Daily briefing feature with weather, calendar, and news

### Exec-Approval Security
- Tools classified by risk level: Safe, Moderate, Dangerous
- Safe tools (search, browse) execute immediately
- Dangerous tools (shell, file write, email send) require `/approve` in chat
- 5-minute approval timeout with clear formatting

### Multi-Channel Architecture
- Abstract `BaseChannel` plugin system
- Telegram is primary, but architecture supports WhatsApp, Discord, Slack, Signal
- Platform-agnostic `ChannelMessage` format
- `ChannelRegistry` for managing multiple connected platforms

## From II-Agent

### Multi-Model LLM Support
- **Anthropic Claude** (native SDK with tool use)
- **OpenAI GPT** (native SDK with function calling)
- **Google Gemini** (native SDK - not just OpenAI-compatible shim)
- **OpenRouter** (access to 100+ models via OpenAI-compatible API)
- Per-user model preferences via `/model` command

### Powerful Tool System
- **Web Search**: Tavily API or DuckDuckGo fallback
- **Browser**: HTTP-based page reading with content extraction
- **Code Execution**: Python sandbox (E2B cloud or local subprocess)
- **File Operations**: Safe workspace-confined file management
- **Shell Commands**: Allowlisted commands with security controls
- **Calendar**: Google Calendar integration
- **Email**: Gmail integration for inbox triage
- **Scheduler**: Cron jobs, reminders, daily briefings
- **Remember/Recall**: AI-managed long-term memory

### Self-Improvement Skills
- Agent can write new tools for itself using `write_skill`
- Custom skills stored in `~/.ii-agent/skills/`
- Auto-discovery and loading of user-created skills

## Unique Features

### Conversation Compaction
- Adaptive context summarization when conversations grow large
- Preserves key facts, tool results, and user information
- Progressive fallback if LLM summarization fails
- Token-aware with configurable thresholds

### Voice Messages
- Speech-to-text via OpenAI Whisper
- Text-to-speech via OpenAI TTS or Edge TTS (free fallback)
- Telegram voice message handling built-in

### Security Model
- User allowlists and pairing codes
- Rate limiting per user
- Exec-approval for dangerous operations
- Workspace-confined file operations
- Shell command allowlisting
- Admin API with bearer token auth

### Deployment
- Docker + Docker Compose support
- Interactive installer script
- Small PC optimized (Raspberry Pi 5, Intel NUC)
- SQLite or PostgreSQL database
- Optional Redis for caching
