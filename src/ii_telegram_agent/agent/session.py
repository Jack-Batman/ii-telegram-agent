"""
Session management for conversations.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Message, MessageRole, Session, User
from .core import Agent, ConversationContext

logger = structlog.get_logger()


class SessionManager:
    """Manages conversation sessions for users."""
    
    def __init__(self, agent: Agent, session_timeout_hours: int = 24):
        self.agent = agent
        self.session_timeout = timedelta(hours=session_timeout_hours)
        self._contexts: dict[str, ConversationContext] = {}
    
    async def get_or_create_session(
        self,
        db: AsyncSession,
        user: User,
    ) -> Session:
        """Get or create an active session for a user."""
        cutoff = datetime.now(timezone.utc) - self.session_timeout
        
        result = await db.execute(
            select(Session)
            .where(
                Session.user_id == user.id,
                Session.is_active == True,
                Session.updated_at > cutoff,
            )
            .order_by(Session.updated_at.desc())
            .limit(1)
        )
        session = result.scalar_one_or_none()
        
        if session is None:
            session = Session(
                user_id=user.id,
                model=user.preferred_model or self.agent.llm.model,
                system_prompt=self.agent.system_prompt,
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)
            logger.info("Created new session", user_id=user.id, session_id=session.id)
        
        return session
    
    async def get_context(
        self,
        db: AsyncSession,
        session: Session,
    ) -> ConversationContext:
        """Get or load conversation context for a session."""
        if session.id in self._contexts:
            return self._contexts[session.id]
        
        context = ConversationContext(
            system_prompt=session.system_prompt or self.agent.system_prompt,
            model=session.model or self.agent.llm.model,
        )
        
        result = await db.execute(
            select(Message)
            .where(Message.session_id == session.id)
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()
        
        for msg in messages:
            from ..llm import LLMMessage
            context.messages.append(LLMMessage(
                role=msg.role,  # type: ignore
                content=msg.content,
            ))
        
        self._contexts[session.id] = context
        return context
    
    async def process_message(
        self,
        db: AsyncSession,
        user: User,
        content: str,
        telegram_message_id: int | None = None,
    ) -> str:
        """Process a message from a user and return the response."""
        session = await self.get_or_create_session(db, user)
        context = await self.get_context(db, session)
        
        user_msg = Message(
            session_id=session.id,
            role=MessageRole.USER.value,
            content=content,
            telegram_message_id=telegram_message_id,
        )
        db.add(user_msg)
        
        response_text, updated_context = await self.agent.process_message(
            content,
            context,
        )
        
        assistant_msg = Message(
            session_id=session.id,
            role=MessageRole.ASSISTANT.value,
            content=response_text,
        )
        db.add(assistant_msg)
        
        session.updated_at = datetime.now(timezone.utc)
        
        await db.commit()
        
        self._contexts[session.id] = updated_context
        
        return response_text
    
    async def clear_session(
        self,
        db: AsyncSession,
        user: User,
    ) -> None:
        """Clear/reset a user's active session."""
        session = await self.get_or_create_session(db, user)
        session.is_active = False
        await db.commit()
        
        if session.id in self._contexts:
            del self._contexts[session.id]
        
        logger.info("Session cleared", user_id=user.id, session_id=session.id)
    
    def evict_context(self, session_id: str) -> None:
        """Evict a context from cache."""
        if session_id in self._contexts:
            del self._contexts[session_id]