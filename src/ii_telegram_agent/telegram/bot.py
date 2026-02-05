"""
Telegram bot implementation.
"""

import asyncio
from datetime import datetime, timedelta, timezone
import random
import string
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telegram import Update
from telegram.ext import Application, ContextTypes

from ..config import Settings, get_settings
from ..models import PairingRequest, User, UserRole

logger = structlog.get_logger()


class TelegramBot:
    """Main Telegram bot class."""
    
    def __init__(
        self,
        settings: Settings | None = None,
        db_session_maker: async_sessionmaker | None = None,
    ):
        self.settings = settings or get_settings()
        self.db_session_maker = db_session_maker
        self.application: Application | None = None
        self._rate_limits: dict[int, list[datetime]] = {}
    
    async def initialize(self) -> None:
        """Initialize the bot application."""
        if not self.settings.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        
        self.application = (
            Application.builder()
            .token(self.settings.telegram_bot_token)
            .build()
        )
        
        from .handlers import setup_handlers
        setup_handlers(self.application, self)
        
        await self.application.initialize()
        logger.info("Telegram bot initialized")
    
    async def start_polling(self) -> None:
        """Start the bot in polling mode."""
        if self.application is None:
            await self.initialize()
        
        await self.application.start()  # type: ignore
        await self.application.updater.start_polling(drop_pending_updates=True)  # type: ignore
        logger.info("Telegram bot started polling")
    
    async def stop(self) -> None:
        """Stop the bot."""
        if self.application:
            await self.application.stop()
            await self.application.shutdown()
            logger.info("Telegram bot stopped")
    
    async def set_webhook(self, webhook_url: str) -> None:
        """Set the webhook URL for receiving updates."""
        if self.application is None:
            await self.initialize()
        
        await self.application.bot.set_webhook(  # type: ignore
            url=webhook_url,
            secret_token=self.settings.telegram_webhook_secret or None,
        )
        logger.info("Webhook set", url=webhook_url)
    
    async def process_update(self, update_data: dict[str, Any]) -> None:
        """Process an incoming webhook update."""
        if self.application is None:
            raise RuntimeError("Bot not initialized")
        
        update = Update.de_json(update_data, self.application.bot)
        await self.application.process_update(update)  # type: ignore
    
    def get_db_session(self) -> AsyncSession:
        """Get a database session."""
        if self.db_session_maker is None:
            raise RuntimeError("Database session maker not set")
        return self.db_session_maker()
    
    async def get_or_create_user(
        self,
        db: AsyncSession,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> User:
        """Get or create a user from Telegram info."""
        result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user is None:
            initial_role = self._determine_initial_role(telegram_id, username)
            
            user = User(
                telegram_id=telegram_id,
                telegram_username=username,
                first_name=first_name,
                last_name=last_name,
                role=initial_role.value,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            logger.info(
                "Created new user",
                telegram_id=telegram_id,
                username=username,
                role=initial_role.value,
            )
        else:
            if username and user.telegram_username != username:
                user.telegram_username = username
            if first_name and user.first_name != first_name:
                user.first_name = first_name
            if last_name and user.last_name != last_name:
                user.last_name = last_name
            user.last_active_at = datetime.now(timezone.utc)
            await db.commit()
        
        return user
    
    def _determine_initial_role(
        self,
        telegram_id: int,
        username: str | None,
    ) -> UserRole:
        """Determine the initial role for a new user."""
        allowed = self.settings.allowed_users_list
        
        if not allowed:
            if self.settings.pairing_enabled:
                return UserRole.PENDING
            return UserRole.USER
        
        str_id = str(telegram_id)
        if str_id in allowed:
            return UserRole.USER
        
        if username and username in allowed:
            return UserRole.USER
        
        if self.settings.pairing_enabled:
            return UserRole.PENDING
        
        return UserRole.BLOCKED
    
    async def create_pairing_request(
        self,
        db: AsyncSession,
        telegram_id: int,
        username: str | None = None,
    ) -> str:
        """Create a pairing request and return the code."""
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        request = PairingRequest(
            telegram_id=telegram_id,
            telegram_username=username,
            code=code,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        db.add(request)
        await db.commit()
        
        logger.info(
            "Pairing request created",
            telegram_id=telegram_id,
            code=code,
        )
        
        return code
    
    async def approve_pairing(
        self,
        db: AsyncSession,
        code: str,
    ) -> bool:
        """Approve a pairing request by code."""
        result = await db.execute(
            select(PairingRequest).where(
                PairingRequest.code == code,
                PairingRequest.is_approved == False,
                PairingRequest.is_expired == False,
                PairingRequest.expires_at > datetime.now(timezone.utc),
            )
        )
        request = result.scalar_one_or_none()
        
        if request is None:
            return False
        
        request.is_approved = True
        
        user_result = await db.execute(
            select(User).where(User.telegram_id == request.telegram_id)
        )
        user = user_result.scalar_one_or_none()
        
        if user:
            user.role = UserRole.USER.value
            user.pairing_code = None
        
        await db.commit()
        
        logger.info(
            "Pairing approved",
            telegram_id=request.telegram_id,
            code=code,
        )
        
        return True
    
    def check_rate_limit(self, telegram_id: int) -> bool:
        """Check if user is within rate limits. Returns True if allowed."""
        now = datetime.now(timezone.utc)
        window = timedelta(minutes=1)
        
        if telegram_id not in self._rate_limits:
            self._rate_limits[telegram_id] = []
        
        self._rate_limits[telegram_id] = [
            t for t in self._rate_limits[telegram_id]
            if now - t < window
        ]
        
        if len(self._rate_limits[telegram_id]) >= self.settings.rate_limit_messages:
            return False
        
        self._rate_limits[telegram_id].append(now)
        return True