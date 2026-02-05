"""
Command-line interface for II-Telegram-Agent.
"""

import argparse
import asyncio
import sys
from pathlib import Path

import structlog
import uvicorn

from .config import get_settings

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer(colors=True),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="ii-telegram",
        description="II-Telegram-Agent - Your personal AI assistant on Telegram",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    serve_parser = subparsers.add_parser("serve", help="Start the bot server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    serve_parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    pair_parser = subparsers.add_parser("pair", help="Manage pairing requests")
    pair_subparsers = pair_parser.add_subparsers(dest="pair_command")

    approve_parser = pair_subparsers.add_parser("approve", help="Approve a pairing request")
    approve_parser.add_argument("code", help="Pairing code to approve")

    list_parser = pair_subparsers.add_parser("list", help="List pending pairing requests")

    config_parser = subparsers.add_parser("config", help="Show configuration")
    config_parser.add_argument("--check", action="store_true", help="Check configuration validity")

    init_parser = subparsers.add_parser("init", help="Initialize the bot (create .env, database)")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "serve":
        run_server(args.host, args.port, args.reload)
    elif args.command == "pair":
        if args.pair_command == "approve":
            asyncio.run(approve_pairing(args.code))
        elif args.pair_command == "list":
            asyncio.run(list_pairing_requests())
        else:
            pair_parser.print_help()
    elif args.command == "config":
        show_config(args.check)
    elif args.command == "init":
        init_bot()
    else:
        parser.print_help()


def run_server(host: str, port: int, reload: bool) -> None:
    """Run the FastAPI server."""
    logger.info("Starting II-Telegram-Agent server", host=host, port=port)

    uvicorn.run(
        "ii_telegram_agent.api.app:create_app",
        host=host,
        port=port,
        reload=reload,
        factory=True,
        log_level="info",
    )


async def approve_pairing(code: str) -> None:
    """Approve a pairing request."""
    from .models import init_database, PairingRequest, User, UserRole
    from sqlalchemy import select
    from datetime import datetime, timezone

    settings = get_settings()
    session_maker = await init_database(settings.database_url)

    async with session_maker() as db:
        result = await db.execute(
            select(PairingRequest).where(
                PairingRequest.code == code,
                PairingRequest.is_approved == False,
                PairingRequest.expires_at > datetime.now(timezone.utc),
            )
        )
        request = result.scalar_one_or_none()

        if request is None:
            logger.error("Pairing code not found or expired", code=code)
            return

        request.is_approved = True

        user_result = await db.execute(
            select(User).where(User.telegram_id == request.telegram_id)
        )
        user = user_result.scalar_one_or_none()

        if user:
            user.role = UserRole.USER.value

        await db.commit()

        logger.info(
            "Pairing approved",
            code=code,
            telegram_id=request.telegram_id,
            username=request.telegram_username,
        )


async def list_pairing_requests() -> None:
    """List pending pairing requests."""
    from .models import init_database, PairingRequest
    from sqlalchemy import select
    from datetime import datetime, timezone

    settings = get_settings()
    session_maker = await init_database(settings.database_url)

    async with session_maker() as db:
        result = await db.execute(
            select(PairingRequest).where(
                PairingRequest.is_approved == False,
                PairingRequest.expires_at > datetime.now(timezone.utc),
            ).order_by(PairingRequest.created_at.desc())
        )
        requests = result.scalars().all()

        if not requests:
            print("No pending pairing requests.")
            return

        print(f"\n{'Code':<10} {'Telegram ID':<15} {'Username':<20} {'Created':<25}")
        print("-" * 70)

        for req in requests:
            created = req.created_at.strftime("%Y-%m-%d %H:%M:%S") if req.created_at else "N/A"
            print(f"{req.code:<10} {req.telegram_id:<15} {req.telegram_username or 'N/A':<20} {created:<25}")


def show_config(check: bool) -> None:
    """Show current configuration."""
    settings = get_settings()

    def mask(value: str) -> str:
        if not value:
            return "(not set)"
        return value[:4] + "..." + value[-4:] if len(value) > 10 else "****"

    print("\n=== II-Telegram-Agent Configuration ===\n")

    print("Server:")
    print(f"  Host: {settings.host}")
    print(f"  Port: {settings.port}")
    print(f"  Debug: {settings.debug}")

    print("\nTelegram:")
    print(f"  Bot Token: {mask(settings.telegram_bot_token)}")
    print(f"  Webhook URL: {settings.telegram_webhook_url or '(polling mode)'}")

    print("\nLLM Providers:")
    print(f"  Default: {settings.default_provider}")
    print(f"  Default Model: {settings.default_model}")
    print(f"  Anthropic Key: {mask(settings.anthropic_api_key)}")
    print(f"  OpenAI Key: {mask(settings.openai_api_key)}")
    print(f"  Google Key: {mask(settings.google_api_key)}")
    print(f"  OpenRouter Key: {mask(settings.openrouter_api_key)}")

    print("\nSecurity:")
    print(f"  Pairing Enabled: {settings.pairing_enabled}")
    print(f"  Allowed Users: {settings.allowed_users or '(all with pairing)'}")
    print(f"  Rate Limit: {settings.rate_limit_messages}/min")

    print("\nFeatures:")
    print(f"  Web Search: {settings.enable_web_search}")
    print(f"  Browser: {settings.enable_browser}")
    print(f"  Code Execution: {settings.enable_code_execution}")

    print("\nDatabase:")
    print(f"  URL: {settings.database_url}")

    if check:
        print("\n=== Configuration Check ===\n")
        errors = []
        warnings = []

        if not settings.telegram_bot_token:
            errors.append("TELEGRAM_BOT_TOKEN is required")

        has_llm = (
            settings.anthropic_api_key or
            settings.openai_api_key or
            settings.google_api_key or
            settings.openrouter_api_key
        )
        if not has_llm:
            errors.append("At least one LLM API key is required")

        if settings.admin_password == "changeme":
            warnings.append("Using default admin password - change ADMIN_PASSWORD in production")

        if settings.jwt_secret == "change-this-secret-in-production":
            warnings.append("Using default JWT secret - change JWT_SECRET in production")

        if errors:
            print("❌ Errors:")
            for e in errors:
                print(f"   - {e}")

        if warnings:
            print("⚠️  Warnings:")
            for w in warnings:
                print(f"   - {w}")

        if not errors and not warnings:
            print("✅ Configuration looks good!")
        elif not errors:
            print("\n✅ Configuration is valid (with warnings)")
        else:
            print("\n❌ Configuration has errors - fix them before starting")


def init_bot() -> None:
    """Initialize the bot with default configuration."""
    env_file = Path(".env")
    data_dir = Path("data")

    data_dir.mkdir(exist_ok=True)

    if not env_file.exists():
        env_content = """# II-Telegram-Agent Configuration

# === REQUIRED ===

# Telegram Bot Token (get from @BotFather)
TELEGRAM_BOT_TOKEN=

# LLM API Keys (set at least one)
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
# GOOGLE_API_KEY=
# OPENROUTER_API_KEY=

# === OPTIONAL ===

# Default LLM provider and model
DEFAULT_PROVIDER=anthropic
DEFAULT_MODEL=claude-sonnet-4-20250514

# Webhook (leave empty for polling mode)
# TELEGRAM_WEBHOOK_URL=https://your-domain.com/webhook/telegram
# TELEGRAM_WEBHOOK_SECRET=your-secret

# Security
ADMIN_PASSWORD=changeme
PAIRING_ENABLED=true
# ALLOWED_USERS=123456789,987654321

# Tools
# TAVILY_API_KEY=
# E2B_API_KEY=

# Server
HOST=0.0.0.0
PORT=8080
DEBUG=false

# Database
DATABASE_URL=sqlite+aiosqlite:///./data/agent.db
"""
        env_file.write_text(env_content)
        print(f"✅ Created {env_file}")
    else:
        print(f"ℹ️  {env_file} already exists")

    print(f"✅ Created {data_dir}")
    print("\n=== Next Steps ===")
    print("1. Edit .env and add your TELEGRAM_BOT_TOKEN")
    print("2. Add at least one LLM API key (ANTHROPIC_API_KEY recommended)")
    print("3. Run: ii-telegram serve")
    print("4. Talk to your bot on Telegram!")


if __name__ == "__main__":
    main()