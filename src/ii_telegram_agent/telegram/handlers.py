"""
Telegram message handlers.
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


def setup_handlers(app: Application, bot: "TelegramBot") -> None:
    """Set up all message handlers."""
    
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
                await update.message.reply_text(  # type: ignore
                    "\ud83d\udc4b Welcome to II-Telegram-Agent!\n\n"
                    "I'm your personal AI assistant running on your own hardware. "
                    "I can help you with:\n\n"
                    "\ud83d\udd0d **Web Search** - Find information online\n"
                    "\ud83d\udcc4 **Read Pages** - Extract content from URLs\n"
                    "\ud83d\udc0d **Run Code** - Execute Python calculations\n"
                    "\ud83d\udcac **Chat** - Have conversations with context\n\n"
                    "Just send me a message to get started!\n\n"
                    "Commands:\n"
                    "/help - Show this help message\n"
                    "/clear - Start a new conversation\n"
                    "/model - Change AI model\n"
                    "/status - Show system status",
                    parse_mode=ParseMode.MARKDOWN,
                )
            else:
                code = await bot.create_pairing_request(
                    db,
                    telegram_id=update.effective_user.id,
                    username=update.effective_user.username,
                )
                await update.message.reply_text(  # type: ignore
                    f"\ud83d\udd10 **Pairing Required**\n\n"
                    f"Your pairing code is: `{code}`\n\n"
                    "Please ask the admin to approve your access using:\n"
                    f"`ii-telegram pair approve {code}`\n\n"
                    "Once approved, send /start again.",
                    parse_mode=ParseMode.MARKDOWN,
                )
    
    async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        await update.message.reply_text(  # type: ignore
            "\ud83e\udd16 **II-Telegram-Agent Help**\n\n"
            "**Commands:**\n"
            "/start - Initialize or restart the bot\n"
            "/help - Show this help message\n"
            "/clear - Clear conversation history\n"
            "/model [name] - View or change AI model\n"
            "/status - Show system status\n\n"
            "**Features:**\n"
            "\u2022 Send any message to chat with the AI\n"
            "\u2022 The AI can search the web for current info\n"
            "\u2022 It can read web pages you link\n"
            "\u2022 It can run Python code for calculations\n\n"
            "**Tips:**\n"
            "\u2022 Be specific in your questions\n"
            "\u2022 You can ask for web searches explicitly\n"
            "\u2022 Conversations have context memory",
            parse_mode=ParseMode.MARKDOWN,
        )
    
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
                await update.message.reply_text("\u274c You don't have access.")  # type: ignore
                return
            
            from ..agent import SessionManager, Agent
            from ..config import get_settings
            from ..llm import create_llm
            
            settings = get_settings()
            agent = Agent(llm=create_llm(settings=settings))
            session_manager = SessionManager(agent)
            
            await session_manager.clear_session(db, user)
            
            await update.message.reply_text(  # type: ignore
                "\ud83d\uddd1\ufe0f Conversation cleared! Send a new message to start fresh.",
            )
    
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
                await update.message.reply_text("\u274c You don't have access.")  # type: ignore
                return
        
        from ..config import get_settings
        settings = get_settings()
        
        status_text = (
            "\ud83d\udcca **System Status**\n\n"
            f"**Default Model:** {settings.default_model}\n"
            f"**Provider:** {settings.default_provider}\n"
            f"**Web Search:** {'\u2705' if settings.enable_web_search else '\u274c'}\n"
            f"**Browser:** {'\u2705' if settings.enable_browser else '\u274c'}\n"
            f"**Code Execution:** {'\u2705' if settings.enable_code_execution else '\u274c'}\n"
            f"**Rate Limit:** {settings.rate_limit_messages}/min\n"
        )
        
        await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)  # type: ignore
    
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
                await update.message.reply_text("\u274c You don't have access.")  # type: ignore
                return
            
            args = context.args or []
            
            if not args:
                from ..config import get_settings
                settings = get_settings()
                
                current = user.preferred_model or settings.default_model
                await update.message.reply_text(  # type: ignore
                    f"\ud83e\udd16 **Current Model:** `{current}`\n\n"
                    "Available models:\n"
                    "\u2022 `claude-sonnet-4-20250514` (Anthropic)\n"
                    "\u2022 `claude-opus-4-20250514` (Anthropic)\n"
                    "\u2022 `gpt-4o` (OpenAI)\n"
                    "\u2022 `gpt-4o-mini` (OpenAI)\n"
                    "\u2022 `gemini-2.0-flash` (Google)\n\n"
                    "Use `/model <name>` to switch.",
                    parse_mode=ParseMode.MARKDOWN,
                )
            else:
                model_name = args[0]
                user.preferred_model = model_name
                await db.commit()
                
                await update.message.reply_text(  # type: ignore
                    f"\u2705 Model changed to `{model_name}`",
                    parse_mode=ParseMode.MARKDOWN,
                )
    
    async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle regular text messages."""
        if not update.effective_user or not update.message or not update.message.text:
            return
        
        if not bot.check_rate_limit(update.effective_user.id):
            await update.message.reply_text(
                "\u23f3 You're sending messages too fast. Please wait a moment.",
            )
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
                    await update.message.reply_text(
                        f"\ud83d\udd10 Pairing required. Your code: `{code}`\n"
                        "Ask an admin to approve it.",
                        parse_mode=ParseMode.MARKDOWN,
                    )
                else:
                    await update.message.reply_text("\u274c You don't have access to this bot.")
                return
            
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,  # type: ignore
                action=ChatAction.TYPING,
            )
            
            try:
                from ..agent import SessionManager, Agent
                from ..config import get_settings
                from ..llm import create_llm
                
                settings = get_settings()
                
                if user.preferred_model:
                    llm_config = settings.get_llm_config()
                    llm_config.model = user.preferred_model
                    llm = create_llm(config=llm_config)
                else:
                    llm = create_llm(settings=settings)
                
                agent = Agent(llm=llm)
                session_manager = SessionManager(agent, settings.session_timeout_hours)
                
                response = await session_manager.process_message(
                    db,
                    user,
                    update.message.text,
                    telegram_message_id=update.message.message_id,
                )
                
                if len(response) <= MAX_MESSAGE_LENGTH:
                    await update.message.reply_text(
                        response,
                        parse_mode=ParseMode.MARKDOWN,
                    )
                else:
                    chunks = [response[i:i+MAX_MESSAGE_LENGTH] for i in range(0, len(response), MAX_MESSAGE_LENGTH)]
                    for chunk in chunks:
                        await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
            
            except Exception as e:
                logger.error("Message processing error", error=str(e), exc_info=True)
                await update.message.reply_text(
                    f"\u274c Sorry, I encountered an error: {str(e)[:200]}",
                )
    
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("clear", clear_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("model", model_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    logger.info("Telegram handlers set up")