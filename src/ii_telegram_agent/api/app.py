"""
FastAPI application factory.
"""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import structlog
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..config import Settings, get_settings
from ..models import init_database
from ..telegram import TelegramBot

logger = structlog.get_logger()

bot: TelegramBot | None = None
db_session_maker = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    global bot, db_session_maker
    
    settings = get_settings()
    
    db_session_maker = await init_database(settings.database_url)
    logger.info("Database initialized")
    
    bot = TelegramBot(settings=settings, db_session_maker=db_session_maker)
    await bot.initialize()
    
    if settings.telegram_webhook_url:
        await bot.set_webhook(settings.telegram_webhook_url)
    else:
        await bot.start_polling()
    
    yield
    
    if bot:
        await bot.stop()
    
    logger.info("Application shutdown complete")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = settings or get_settings()
    
    app = FastAPI(
        title="II-Telegram-Agent",
        description="AI Assistant for Telegram powered by II-Agent",
        version="1.0.0",
        lifespan=lifespan,
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
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
                <h1 class="text-4xl font-bold mb-8">\ud83e\udd16 II-Telegram-Agent</h1>
                <div class="grid md:grid-cols-2 gap-6">
                    <div class="bg-gray-800 p-6 rounded-lg">
                        <h2 class="text-2xl font-semibold mb-4">Status</h2>
                        <p class="text-green-400">\u2705 Bot is running</p>
                        <p class="text-gray-400 mt-2">Check /api/health for details</p>
                    </div>
                    <div class="bg-gray-800 p-6 rounded-lg">
                        <h2 class="text-2xl font-semibold mb-4">Quick Links</h2>
                        <ul class="space-y-2">
                            <li><a href="/api/health" class="text-blue-400 hover:underline">Health Check</a></li>
                            <li><a href="/docs" class="text-blue-400 hover:underline">API Documentation</a></li>
                            <li><a href="/api/stats" class="text-blue-400 hover:underline">Usage Statistics</a></li>
                        </ul>
                    </div>
                </div>
                <div class="mt-8 bg-gray-800 p-6 rounded-lg">
                    <h2 class="text-2xl font-semibold mb-4">Getting Started</h2>
                    <ol class="list-decimal list-inside space-y-2 text-gray-300">
                        <li>Set your TELEGRAM_BOT_TOKEN in .env</li>
                        <li>Add your LLM API key (ANTHROPIC_API_KEY or OPENAI_API_KEY)</li>
                        <li>Start chatting with your bot on Telegram!</li>
                    </ol>
                </div>
            </div>
        </body>
        </html>
        """
    
    @app.get("/api/health")
    async def health_check():
        """Health check endpoint."""
        settings = get_settings()
        return {
            "status": "healthy",
            "bot_running": bot is not None,
            "telegram_configured": bool(settings.telegram_bot_token),
            "llm_configured": bool(
                settings.anthropic_api_key or 
                settings.openai_api_key or 
                settings.google_api_key
            ),
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
    
    class WebhookUpdate(BaseModel):
        """Telegram webhook update model."""
        update_id: int
        message: dict[str, Any] | None = None
        edited_message: dict[str, Any] | None = None
        callback_query: dict[str, Any] | None = None
    
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