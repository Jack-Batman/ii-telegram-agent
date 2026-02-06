"""
Telegram message handlers.

Fixed critical bug: Agent and SessionManager are now shared singletons
instead of being recreated on every message (which destroyed all context).

Includes:
- Voice message support (STT/TTS)
- Exec-approval /approve and /deny commands
- /remember and /soul commands
- Proper long-message splitting with Markdown safety
"""

from typing import TYPE_CHECKING

import structlog
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode, ChatAction

if TYPE_CHECKING:
    from .bot import TelegramBot

logger = structlog.get_logger()

MAX_MESSAGE_LENGTH = 4000


def _split_message(text: str, max_len: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Split a long message into chunks, trying to break at newlines."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        # Try to break at a newline
        split_at = text.rfind("\n", 0, max_len)
        if split_at < max_len // 2:
            # No good newline, break at max_len
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")

    return chunks


async def _safe_reply(message, text: str, parse_mode=ParseMode.MARKDOWN) -> None:
    """Reply with fallback to plain text if Markdown parsing fails."""
    chunks = _split_message(text)
    for chunk in chunks:
        try:
            await message.reply_text(chunk, parse_mode=parse_mode)
        except Exception:
            # Markdown parsing failed; send as plain text
            try:
                await message.reply_text(chunk)
            except Exception as e:
                logger.error("Failed to send message", error=str(e))


def setup_handlers(app: Application, bot: "TelegramBot") -> None:
    """Set up all message handlers."""

    # ------------------------------------------------------------------ #
    # Shared Agent + SessionManager (created once, reused across messages)
    # ------------------------------------------------------------------ #
    _agent_cache: dict[str, object] = {}

    def _get_agent_and_session_manager():
        """Get or create the singleton Agent and SessionManager."""
        if "agent" not in _agent_cache:
            from ..agent import Agent, SessionManager
            from ..config import get_settings
            from ..llm import create_llm

            settings = get_settings()
            llm = create_llm(settings=settings)
            agent = Agent(llm=llm)
            session_manager = SessionManager(agent, settings.session_timeout_hours)

            _agent_cache["agent"] = agent
            _agent_cache["session_manager"] = session_manager
            _agent_cache["settings"] = settings

        return _agent_cache["agent"], _agent_cache["session_manager"], _agent_cache["settings"]

    # ------------------------------------------------------------------ #
    # /start
    # ------------------------------------------------------------------ #
    async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if not update.effective_user or not update.effective_chat:
            return

        async with bot.get_db_session() as db:
            user = await bot.get_or_create_user(
                db,
                telegram_id=update.effective_user.id,
                username=update.effective_user.username,
                first_name=update.effective_user.first_name,
                last_name=update.effective_user.last_name,
            )

            if user.is_allowed:
                agent, _, _ = _get_agent_and_session_manager()
                name = agent.get_assistant_name()

                await _safe_reply(
                    update.message,
                    f"Hello! I'm **{name}**, your personal AI assistant.\n\n"
                    "I'm running on your own hardware and I can help with:\n\n"
                    "- Web search and research\n"
                    "- Reading web pages and articles\n"
                    "- Running Python code\n"
                    "- Managing files, calendar, and email\n"
                    "- Setting reminders and schedules\n"
                    "- Remembering things across conversations\n\n"
                    "**Commands:**\n"
                    "`/help` - Full help\n"
                    "`/clear` - New conversation\n"
                    "`/model` - Change AI model\n"
                    "`/status` - System status\n"
                    "`/remember <text>` - Save to memory\n"
                    "`/soul` - View personality\n"
                    "`/approve <id>` - Approve a pending action\n"
                    "`/deny <id>` - Deny a pending action\n\n"
                    "Just send me a message to get started!",
                )
            else:
                code = await bot.create_pairing_request(
                    db,
                    telegram_id=update.effective_user.id,
                    username=update.effective_user.username,
                )
                await _safe_reply(
                    update.message,
                    f"**Pairing Required**\n\n"
                    f"Your pairing code is: `{code}`\n\n"
                    "Please ask the admin to approve your access using:\n"
                    f"`ii-telegram pair approve {code}`\n\n"
                    "Once approved, send /start again.",
                )

    # ------------------------------------------------------------------ #
    # /help
    # ------------------------------------------------------------------ #
    async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        await _safe_reply(
            update.message,
            "**II-Telegram-Agent Help**\n\n"
            "**Chat Commands:**\n"
            "`/start` - Initialize the bot\n"
            "`/help` - Show this help\n"
            "`/clear` - Clear conversation history\n"
            "`/model [name]` - View/change AI model\n"
            "`/status` - System status\n\n"
            "**Memory Commands:**\n"
            "`/remember <text>` - Save something to memory\n"
            "`/soul` - View personality settings\n\n"
            "**Approval Commands:**\n"
            "`/approve <id>` - Approve a pending action\n"
            "`/deny <id>` - Deny a pending action\n"
            "`/pending` - Show pending approvals\n\n"
            "**Features:**\n"
            "- Send text messages for AI conversation\n"
            "- Send voice messages for transcription + AI response\n"
            "- The AI can search the web, read pages, run code\n"
            "- It remembers important info across sessions\n"
            "- Dangerous actions require your /approve first\n\n"
            "**Tips:**\n"
            "- Be specific in your questions\n"
            "- Ask it to remember things for later\n"
            "- Conversations maintain context automatically",
        )

    # ------------------------------------------------------------------ #
    # /clear
    # ------------------------------------------------------------------ #
    async def clear_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /clear command."""
        if not update.effective_user:
            return

        async with bot.get_db_session() as db:
            user = await bot.get_or_create_user(
                db,
                telegram_id=update.effective_user.id,
                username=update.effective_user.username,
            )

            if not user.is_allowed:
                await _safe_reply(update.message, "You don't have access.")
                return

            _, session_manager, _ = _get_agent_and_session_manager()
            await session_manager.clear_session(db, user)

            await _safe_reply(
                update.message,
                "Conversation cleared! Long-term memories are preserved.\n"
                "Send a new message to start fresh.",
            )

    # ------------------------------------------------------------------ #
    # /status
    # ------------------------------------------------------------------ #
    async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        if not update.effective_user:
            return

        async with bot.get_db_session() as db:
            user = await bot.get_or_create_user(
                db,
                telegram_id=update.effective_user.id,
                username=update.effective_user.username,
            )

            if not user.is_allowed:
                await _safe_reply(update.message, "You don't have access.")
                return

        _, _, settings = _get_agent_and_session_manager()

        features = []
        if settings.enable_web_search:
            features.append("Web Search")
        if settings.enable_browser:
            features.append("Browser")
        if settings.enable_code_execution:
            features.append("Code Execution")
        if settings.enable_file_operations:
            features.append("File Operations")
        if settings.enable_voice:
            features.append("Voice (STT/TTS)")

        status_text = (
            "**System Status**\n\n"
            f"**Model:** `{settings.default_model}`\n"
            f"**Provider:** {settings.default_provider}\n"
            f"**Features:** {', '.join(features) if features else 'None'}\n"
            f"**Rate Limit:** {settings.rate_limit_messages}/min\n"
            f"**Context Window:** {settings.max_context_messages} messages\n"
        )

        await _safe_reply(update.message, status_text)

    # ------------------------------------------------------------------ #
    # /model
    # ------------------------------------------------------------------ #
    async def model_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /model command."""
        if not update.effective_user:
            return

        async with bot.get_db_session() as db:
            user = await bot.get_or_create_user(
                db,
                telegram_id=update.effective_user.id,
                username=update.effective_user.username,
            )

            if not user.is_allowed:
                await _safe_reply(update.message, "You don't have access.")
                return

            args = context.args or []

            if not args:
                _, _, settings = _get_agent_and_session_manager()
                current = user.preferred_model or settings.default_model

                await _safe_reply(
                    update.message,
                    f"**Current Model:** `{current}`\n\n"
                    "**Available models:**\n"
                    "- `claude-sonnet-4-20250514` (Anthropic)\n"
                    "- `claude-opus-4-20250514` (Anthropic)\n"
                    "- `gpt-4o` (OpenAI)\n"
                    "- `gpt-4o-mini` (OpenAI)\n"
                    "- `gemini-2.0-flash` (Google)\n"
                    "- `gemini-2.5-pro` (Google)\n\n"
                    "Use `/model <name>` to switch.",
                )
            else:
                model_name = args[0]
                user.preferred_model = model_name
                await db.commit()

                await _safe_reply(
                    update.message,
                    f"Model changed to `{model_name}`",
                )

    # ------------------------------------------------------------------ #
    # /remember
    # ------------------------------------------------------------------ #
    async def remember_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /remember command - quick save to memory."""
        if not update.effective_user or not context.args:
            await _safe_reply(update.message, "Usage: `/remember <text to save>`")
            return

        async with bot.get_db_session() as db:
            user = await bot.get_or_create_user(
                db,
                telegram_id=update.effective_user.id,
                username=update.effective_user.username,
            )

            if not user.is_allowed:
                return

        text = " ".join(context.args)
        agent, _, _ = _get_agent_and_session_manager()
        agent.memory_manager.add_fact(text)

        await _safe_reply(update.message, f"Saved to memory: _{text}_")

    # ------------------------------------------------------------------ #
    # /soul
    # ------------------------------------------------------------------ #
    async def soul_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /soul command - show personality settings."""
        if not update.effective_user:
            return

        async with bot.get_db_session() as db:
            user = await bot.get_or_create_user(
                db,
                telegram_id=update.effective_user.id,
                username=update.effective_user.username,
            )
            if not user.is_allowed:
                return

        agent, _, _ = _get_agent_and_session_manager()
        soul_content = agent.soul_manager.read()

        # Truncate if too long
        if len(soul_content) > 3000:
            soul_content = soul_content[:3000] + "\n\n_...truncated_"

        await _safe_reply(update.message, f"**Current Personality:**\n\n{soul_content}")

    # ------------------------------------------------------------------ #
    # /approve and /deny (exec-approval system)
    # ------------------------------------------------------------------ #
    async def approve_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /approve command for exec-approval."""
        if not update.effective_user or not context.args:
            await _safe_reply(update.message, "Usage: `/approve <approval_id>`")
            return

        async with bot.get_db_session() as db:
            user = await bot.get_or_create_user(
                db,
                telegram_id=update.effective_user.id,
                username=update.effective_user.username,
            )
            if not user.is_allowed:
                return

        from ..tools.exec_approval import get_approval_manager
        manager = get_approval_manager()

        approval_id = context.args[0]
        if manager.approve(approval_id):
            await _safe_reply(update.message, f"Approved: `{approval_id}`")
        else:
            await _safe_reply(update.message, f"Approval `{approval_id}` not found or expired.")

    async def deny_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /deny command for exec-approval."""
        if not update.effective_user or not context.args:
            await _safe_reply(update.message, "Usage: `/deny <approval_id>`")
            return

        async with bot.get_db_session() as db:
            user = await bot.get_or_create_user(
                db,
                telegram_id=update.effective_user.id,
                username=update.effective_user.username,
            )
            if not user.is_allowed:
                return

        from ..tools.exec_approval import get_approval_manager
        manager = get_approval_manager()

        approval_id = context.args[0]
        if manager.deny(approval_id):
            await _safe_reply(update.message, f"Denied: `{approval_id}`")
        else:
            await _safe_reply(update.message, f"Approval `{approval_id}` not found or expired.")

    async def pending_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /pending command - list pending approvals."""
        if not update.effective_user:
            return

        async with bot.get_db_session() as db:
            user = await bot.get_or_create_user(
                db,
                telegram_id=update.effective_user.id,
                username=update.effective_user.username,
            )
            if not user.is_allowed:
                return

        from ..tools.exec_approval import get_approval_manager
        manager = get_approval_manager()
        pending = manager.list_pending()

        if not pending:
            await _safe_reply(update.message, "No pending approvals.")
            return

        text = f"**Pending Approvals ({len(pending)}):**\n\n"
        for p in pending:
            text += p.format_for_display() + "\n\n"

        await _safe_reply(update.message, text)

    # ------------------------------------------------------------------ #
    # Voice message handler
    # ------------------------------------------------------------------ #
    async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle voice messages - transcribe and process."""
        if not update.effective_user or not update.message or not update.message.voice:
            return

        if not bot.check_rate_limit(update.effective_user.id):
            await _safe_reply(update.message, "You're sending messages too fast. Please wait.")
            return

        async with bot.get_db_session() as db:
            user = await bot.get_or_create_user(
                db,
                telegram_id=update.effective_user.id,
                username=update.effective_user.username,
                first_name=update.effective_user.first_name,
                last_name=update.effective_user.last_name,
            )

            if not user.is_allowed:
                return

            _, _, settings = _get_agent_and_session_manager()

            if not settings.enable_voice:
                await _safe_reply(
                    update.message,
                    "Voice messages are not enabled. Set `ENABLE_VOICE=true` in your config.",
                )
                return

            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action=ChatAction.TYPING,
            )

            try:
                # Download voice file
                voice_file = await update.message.voice.get_file()
                voice_bytes = await voice_file.download_as_bytearray()

                # Transcribe
                from ..voice import VoiceProcessor
                processor = VoiceProcessor(
                    openai_api_key=settings.openai_api_key,
                )

                transcribed_text = await processor.transcribe(bytes(voice_bytes))

                if not transcribed_text:
                    await _safe_reply(update.message, "I couldn't understand the voice message.")
                    return

                # Show what was heard
                await _safe_reply(
                    update.message,
                    f"_Heard: {transcribed_text}_",
                )

                # Process as regular message
                agent, session_manager, _ = _get_agent_and_session_manager()

                response = await session_manager.process_message(
                    db,
                    user,
                    transcribed_text,
                    telegram_message_id=update.message.message_id,
                )

                await _safe_reply(update.message, response)

            except Exception as e:
                logger.error("Voice processing error", error=str(e), exc_info=True)
                await _safe_reply(
                    update.message,
                    f"Error processing voice message: {str(e)[:200]}",
                )

    # ------------------------------------------------------------------ #
    # Regular text message handler
    # ------------------------------------------------------------------ #
    async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle regular text messages."""
        if not update.effective_user or not update.message or not update.message.text:
            return

        if not bot.check_rate_limit(update.effective_user.id):
            await _safe_reply(update.message, "You're sending messages too fast. Please wait.")
            return

        async with bot.get_db_session() as db:
            user = await bot.get_or_create_user(
                db,
                telegram_id=update.effective_user.id,
                username=update.effective_user.username,
                first_name=update.effective_user.first_name,
                last_name=update.effective_user.last_name,
            )

            if not user.is_allowed:
                if bot.settings.pairing_enabled:
                    code = await bot.create_pairing_request(
                        db,
                        telegram_id=update.effective_user.id,
                        username=update.effective_user.username,
                    )
                    await _safe_reply(
                        update.message,
                        f"Pairing required. Your code: `{code}`\n"
                        "Ask an admin to approve it.",
                    )
                else:
                    await _safe_reply(update.message, "You don't have access to this bot.")
                return

            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action=ChatAction.TYPING,
            )

            try:
                agent, session_manager, settings = _get_agent_and_session_manager()

                # Use user's preferred model if set
                if user.preferred_model and user.preferred_model != agent.llm.model:
                    from ..llm import create_llm
                    llm_config = settings.get_llm_config()
                    llm_config.model = user.preferred_model
                    agent.llm = create_llm(config=llm_config)

                response = await session_manager.process_message(
                    db,
                    user,
                    update.message.text,
                    telegram_message_id=update.message.message_id,
                )

                await _safe_reply(update.message, response)

            except Exception as e:
                logger.error("Message processing error", error=str(e), exc_info=True)
                await _safe_reply(
                    update.message,
                    f"Sorry, I encountered an error: {str(e)[:200]}",
                )

    # ------------------------------------------------------------------ #
    # Register all handlers
    # ------------------------------------------------------------------ #
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("clear", clear_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("model", model_handler))
    app.add_handler(CommandHandler("remember", remember_handler))
    app.add_handler(CommandHandler("soul", soul_handler))
    app.add_handler(CommandHandler("approve", approve_handler))
    app.add_handler(CommandHandler("deny", deny_handler))
    app.add_handler(CommandHandler("pending", pending_handler))
    app.add_handler(MessageHandler(filters.VOICE, voice_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info("Telegram handlers set up (with voice, exec-approval, memory commands)")
