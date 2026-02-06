"""
FastAPI application factory.

Manages the lifecycle of:
- Database connection
- Telegram bot (polling or webhook)
- Scheduler (cron jobs, heartbeats, reminders)
- Proactive messaging (scheduler -> Telegram)
"""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import structlog
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from ..config import Settings, get_settings
from ..models import init_database
from ..telegram import TelegramBot

logger = structlog.get_logger()

bot: TelegramBot | None = None
db_session_maker = None
scheduler_instance = None


async def _scheduler_callback(task):
    """Called when a scheduled task fires. Sends the message to the bot owner."""
    if bot is None or db_session_maker is None:
        return

    try:
        settings = get_settings()
        allowed_users = settings.allowed_users_list

        if not allowed_users or not bot.application:
            logger.warning("Cannot send scheduled message: no allowed users or bot not ready")
            return

        # Send to the first allowed user (assumed to be the owner)
        owner_id = allowed_users[0]
        try:
            owner_id_int = int(owner_id)
        except ValueError:
            logger.warning("Cannot send scheduled message: owner ID is not numeric", owner_id=owner_id)
            return

        message_text = f"**Scheduled: {task.name}**\n\n{task.message}"

        await bot.application.bot.send_message(
            chat_id=owner_id_int,
            text=message_text,
            parse_mode="Markdown",
        )

        logger.info("Sent scheduled message", task_name=task.name, user_id=owner_id_int)

    except Exception as e:
        logger.error("Failed to send scheduled message", error=str(e), task=task.name)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    global bot, db_session_maker, scheduler_instance

    settings = get_settings()

    # Initialize database
    db_session_maker = await init_database(settings.database_url)
    logger.info("Database initialized")

    # Initialize Telegram bot
    bot = TelegramBot(settings=settings, db_session_maker=db_session_maker)
    await bot.initialize()

    if settings.telegram_webhook_url:
        await bot.set_webhook(settings.telegram_webhook_url)
    else:
        await bot.start_polling()

    # Initialize and start the scheduler with Telegram integration
    try:
        from ..scheduler import Scheduler
        scheduler_instance = Scheduler(callback=_scheduler_callback)
        scheduler_instance.start()
        logger.info("Scheduler started", task_count=len(scheduler_instance.tasks))
    except Exception as e:
        logger.warning("Failed to start scheduler", error=str(e))

    yield

    # Shutdown
    if scheduler_instance:
        scheduler_instance.stop()

    if bot:
        await bot.stop()

    logger.info("Application shutdown complete")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = settings or get_settings()

    app = FastAPI(
        title="II-Telegram-Agent",
        description="AI Assistant for Telegram powered by II-Agent",
        version="1.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------ #
    # Admin dashboard
    # ------------------------------------------------------------------ #
    @app.get("/", response_class=HTMLResponse)
    async def index():
        """Serve the admin dashboard."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>II-Telegram-Agent</title>
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="bg-gray-900 text-white min-h-screen">
            <div class="container mx-auto px-4 py-8">
                <h1 class="text-4xl font-bold mb-2">II-Telegram-Agent</h1>
                <p class="text-gray-400 mb-8">Your personal AI assistant on Telegram</p>
                <div class="grid md:grid-cols-3 gap-6">
                    <div class="bg-gray-800 p-6 rounded-lg">
                        <h2 class="text-2xl font-semibold mb-4">Status</h2>
                        <p class="text-green-400 text-lg">Bot is running</p>
                        <p class="text-gray-400 mt-2">Check /api/health for details</p>
                    </div>
                    <div class="bg-gray-800 p-6 rounded-lg">
                        <h2 class="text-2xl font-semibold mb-4">Features</h2>
                        <ul class="space-y-1 text-gray-300">
                            <li>Multi-model AI (Claude, GPT, Gemini)</li>
                            <li>Soul/Memory personality system</li>
                            <li>Web search & browser tools</li>
                            <li>Code execution sandbox</li>
                            <li>Exec-approval security</li>
                            <li>Voice messages (STT/TTS)</li>
                            <li>Proactive heartbeat scheduler</li>
                        </ul>
                    </div>
                    <div class="bg-gray-800 p-6 rounded-lg">
                        <h2 class="text-2xl font-semibold mb-4">Links</h2>
                        <ul class="space-y-2">
                            <li><a href="/api/health" class="text-blue-400 hover:underline">Health Check</a></li>
                            <li><a href="/docs" class="text-blue-400 hover:underline">API Docs (Swagger)</a></li>
                            <li><a href="/api/stats" class="text-blue-400 hover:underline">Statistics</a></li>
                            <li><a href="/api/scheduler/tasks" class="text-blue-400 hover:underline">Scheduled Tasks</a></li>
                        </ul>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

    # ------------------------------------------------------------------ #
    # Health & Stats
    # ------------------------------------------------------------------ #
    @app.get("/api/health")
    async def health_check():
        """Health check endpoint."""
        settings = get_settings()
        return {
            "status": "healthy",
            "version": "1.1.0",
            "bot_running": bot is not None,
            "telegram_configured": bool(settings.telegram_bot_token),
            "llm_configured": bool(
                settings.anthropic_api_key
                or settings.openai_api_key
                or settings.google_api_key
            ),
            "scheduler_running": scheduler_instance is not None and scheduler_instance._running,
            "database": "connected",
        }

    @app.get("/api/stats")
    async def get_stats():
        """Get usage statistics."""
        if db_session_maker is None:
            raise HTTPException(status_code=500, detail="Database not initialized")

        from sqlalchemy import func, select
        from ..models import User, Session, Message

        async with db_session_maker() as db:
            user_count = await db.scalar(select(func.count(User.id)))
            session_count = await db.scalar(select(func.count(Session.id)))
            message_count = await db.scalar(select(func.count(Message.id)))

        return {
            "users": user_count,
            "sessions": session_count,
            "messages": message_count,
        }

    # ------------------------------------------------------------------ #
    # Scheduler API
    # ------------------------------------------------------------------ #
    @app.get("/api/scheduler/tasks")
    async def list_scheduler_tasks():
        """List all scheduled tasks."""
        if scheduler_instance is None:
            return {"tasks": [], "error": "Scheduler not running"}

        tasks = scheduler_instance.list_tasks()
        return {
            "tasks": [t.to_dict() for t in tasks],
            "count": len(tasks),
        }

    # ------------------------------------------------------------------ #
    # Telegram Webhook
    # ------------------------------------------------------------------ #
    @app.post("/webhook/telegram")
    async def telegram_webhook(
        request: Request,
        x_telegram_bot_api_secret_token: str | None = Header(None),
    ):
        """Handle Telegram webhook updates."""
        settings = get_settings()

        if settings.telegram_webhook_secret:
            if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
                raise HTTPException(status_code=401, detail="Invalid secret token")

        if bot is None:
            raise HTTPException(status_code=500, detail="Bot not initialized")

        update_data = await request.json()

        try:
            await bot.process_update(update_data)
        except Exception as e:
            logger.error("Webhook processing error", error=str(e))

        return {"ok": True}

    # ------------------------------------------------------------------ #
    # Pairing & User Management
    # ------------------------------------------------------------------ #
    class PairApproveRequest(BaseModel):
        """Pairing approval request."""
        code: str

    @app.post("/api/pair/approve")
    async def approve_pairing(
        request: PairApproveRequest,
        authorization: str = Header(...),
    ):
        """Approve a pairing request."""
        settings = get_settings()

        expected = f"Bearer {settings.admin_password}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail="Invalid authorization")

        if bot is None or db_session_maker is None:
            raise HTTPException(status_code=500, detail="Service not ready")

        async with db_session_maker() as db:
            success = await bot.approve_pairing(db, request.code)

        if success:
            return {"status": "approved", "code": request.code}
        else:
            raise HTTPException(status_code=404, detail="Pairing code not found or expired")

    @app.get("/api/users")
    async def list_users(
        authorization: str = Header(...),
    ):
        """List all users."""
        settings = get_settings()

        expected = f"Bearer {settings.admin_password}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail="Invalid authorization")

        if db_session_maker is None:
            raise HTTPException(status_code=500, detail="Database not initialized")

        from sqlalchemy import select
        from ..models import User

        async with db_session_maker() as db:
            result = await db.execute(select(User).order_by(User.created_at.desc()))
            users = result.scalars().all()

        return {
            "users": [
                {
                    "id": u.id,
                    "telegram_id": u.telegram_id,
                    "username": u.telegram_username,
                    "name": f"{u.first_name or ''} {u.last_name or ''}".strip(),
                    "role": u.role,
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                    "last_active": u.last_active_at.isoformat() if u.last_active_at else None,
                }
                for u in users
            ]
        }

    return app
