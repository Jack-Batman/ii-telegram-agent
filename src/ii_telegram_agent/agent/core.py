"""
Core agent implementation with Soul, Memory, Compaction, and Exec-Approval.

This is the brain of the system. It:
1. Builds a system prompt from SOUL.md + USER.md + MEMORY.md
2. Processes messages through the LLM with tool support
3. Handles conversation compaction when context grows too large
4. Routes dangerous tool calls through the exec-approval system
5. Manages the remember/recall memory tools
"""

from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import structlog

from ..config import Settings, get_settings
from ..llm import BaseLLM, LLMMessage, LLMResponse, ToolCall, create_llm
from ..tools import ToolRegistry, get_tool_registry
from ..memory import MemoryManager, SoulManager, UserProfileManager

logger = structlog.get_logger()

# Fallback system prompt if soul files don't exist
DEFAULT_SYSTEM_PROMPT = """You are II-Agent, a helpful AI assistant running on the user's own hardware via Telegram.

You have access to powerful tools that help you accomplish tasks:
- **web_search**: Search the internet for current information
- **browse_webpage**: Visit and read web pages
- **execute_code**: Run Python code for calculations and data processing
- **remember**: Save important information to long-term memory
- **recall**: Retrieve information from your memory
- **run_command**: Execute shell commands (requires user approval)
- **read_file** / **write_file**: File operations in the workspace
- **set_reminder**: Set time-based reminders
- **check_email**: Check Gmail inbox
- **get_calendar**: View upcoming calendar events

Guidelines:
1. Be helpful, accurate, and concise
2. Use tools when you need current information or to perform calculations
3. Explain your reasoning when helpful
4. If you're unsure, say so and offer to search for information
5. Format responses clearly using Markdown (Telegram supports basic Markdown)
6. Remember important information the user shares for future reference
7. Reference past conversations and memories when relevant
8. For dangerous operations (shell, file write, email), explain what you'll do first

You're running on the user's personal device, so maintain their privacy and security."""


@dataclass
class ConversationContext:
    """Context for a conversation."""

    messages: list[LLMMessage] = field(default_factory=list)
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    model: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    compaction_count: int = 0  # Track how many times we've compacted

    def add_user_message(self, content: str) -> None:
        """Add a user message."""
        self.messages.append(LLMMessage(role="user", content=content))

    def add_assistant_message(
        self, content: str, tool_calls: list[ToolCall] | None = None
    ) -> None:
        """Add an assistant message."""
        self.messages.append(LLMMessage(
            role="assistant",
            content=content,
            tool_calls=tool_calls,
        ))

    def add_tool_result(self, tool_call_id: str, result: str, tool_name: str = "") -> None:
        """Add a tool result."""
        self.messages.append(LLMMessage(
            role="tool",
            content=result,
            tool_call_id=tool_call_id,
            name=tool_name,
        ))

    def truncate(self, max_messages: int = 50) -> None:
        """Truncate message history to keep context manageable."""
        if len(self.messages) > max_messages:
            self.messages = self.messages[-max_messages:]

    @property
    def message_count(self) -> int:
        """Get the number of messages."""
        return len(self.messages)


class Agent:
    """Main agent class that processes messages and generates responses.

    Integrates with Soul, User Profile, Memory, Compaction, and Exec-Approval
    systems for personalized, context-aware, safe conversations.
    """

    def __init__(
        self,
        llm: BaseLLM | None = None,
        tool_registry: ToolRegistry | None = None,
        settings: Settings | None = None,
        system_prompt: str | None = None,
        workspace_dir: str | None = None,
    ):
        self.settings = settings or get_settings()
        self.llm = llm or create_llm(settings=self.settings)
        self.tool_registry = tool_registry or get_tool_registry()
        self.max_tool_iterations = 10

        # Initialize memory systems
        self.soul_manager = SoulManager(workspace_dir)
        self.user_profile = UserProfileManager(workspace_dir)
        self.memory_manager = MemoryManager(workspace_dir)

        # Compaction config
        from .compaction import CompactionConfig
        self.compaction_config = CompactionConfig(
            max_context_tokens=100_000,
            compaction_threshold=0.7,
            keep_recent_messages=self.settings.max_context_messages // 2,
            enabled=True,
        )

        # Build system prompt from soul + user + memory
        if system_prompt:
            self.system_prompt = system_prompt
        else:
            self.system_prompt = self._build_system_prompt()

        # Register memory tools
        self._register_memory_tools()

    def _build_system_prompt(self) -> str:
        """Build a comprehensive system prompt from soul, user, and memory."""
        try:
            parts = []

            # Get soul-based system prompt
            soul_prompt = self.soul_manager.get_system_prompt()
            parts.append(soul_prompt)

            # Add tool information from registry
            tool_names = self.tool_registry.list_tools()
            if tool_names:
                parts.append("""
## Available Tools
You have access to these tools:
""" + "\n".join(f"- **{name}**" for name in tool_names) + """

Use tools when you need current information, to perform calculations, manage files, or remember important details.
Some tools (like shell commands and file writes) require user approval before execution.""")

            # Add user context
            user_context = self.user_profile.get_context_for_prompt()
            if user_context and "No user profile" not in user_context:
                parts.append(f"""
## About the User
{user_context}
""")

            # Add memory context
            memory_context = self.memory_manager.get_context_for_prompt()
            if memory_context and "No memories stored" not in memory_context:
                parts.append(f"""
## Your Memory
{memory_context}
""")

            # Add runtime guidelines
            parts.append("""
## Guidelines
1. Be helpful, accurate, and concise
2. Reference relevant memories and user information naturally
3. Save important new information the user shares using the remember tool
4. If you're unsure, say so and offer to search for information
5. Format responses clearly using Markdown
6. You're running on the user's personal device - maintain their privacy
7. For shell commands or file writes, explain what you'll do before doing it
""")

            return "\n".join(parts)

        except Exception as e:
            logger.error("Error building system prompt", error=str(e))
            return DEFAULT_SYSTEM_PROMPT

    def _register_memory_tools(self):
        """Register memory-related tools."""
        from ..tools.base import Tool, ToolParameter, ToolResult

        async def remember_tool(memory: str, category: str = "Important Facts") -> ToolResult:
            """Save information to long-term memory."""
            try:
                valid_categories = [
                    "User Preferences",
                    "Important Facts",
                    "Ongoing Projects",
                    "Reminders & Notes",
                ]

                if category not in valid_categories:
                    category = "Important Facts"

                self.memory_manager.add_memory(category, memory)
                return ToolResult(
                    success=True,
                    output=f"Saved to memory ({category}): {memory}",
                )
            except Exception as e:
                return ToolResult(success=False, error=str(e))

        async def recall_tool(query: str) -> ToolResult:
            """Search and retrieve information from memory."""
            try:
                matches = self.memory_manager.search(query)

                if matches:
                    result = "Found in memory:\n" + "\n".join(matches)
                else:
                    recent = self.memory_manager.get_recent_memories(5)
                    if recent:
                        result = (
                            f"No exact match for '{query}'. Recent memories:\n"
                            + "\n".join(f"- {m}" for m in recent)
                        )
                    else:
                        result = "No memories found."

                return ToolResult(success=True, output=result)
            except Exception as e:
                return ToolResult(success=False, error=str(e))

        # Register the tools
        remember = Tool(
            name="remember",
            description=(
                "Save important information to long-term memory. Use this when the user "
                "shares something worth remembering for future conversations."
            ),
            parameters=[
                ToolParameter(
                    name="memory",
                    param_type="string",
                    description="The information to remember",
                    required=True,
                ),
                ToolParameter(
                    name="category",
                    param_type="string",
                    description="Category: 'User Preferences', 'Important Facts', 'Ongoing Projects', or 'Reminders & Notes'",
                    required=False,
                ),
            ],
            handler=remember_tool,
        )

        recall = Tool(
            name="recall",
            description="Search and retrieve information from long-term memory. Use this to find previously saved information.",
            parameters=[
                ToolParameter(
                    name="query",
                    param_type="string",
                    description="What to search for in memory",
                    required=True,
                ),
            ],
            handler=recall_tool,
        )

        self.tool_registry.register(remember)
        self.tool_registry.register(recall)

    def refresh_context(self):
        """Refresh the system prompt with updated memory context."""
        self.system_prompt = self._build_system_prompt()

    def get_assistant_name(self) -> str:
        """Get the assistant's name from soul."""
        return self.soul_manager.get_name()

    def get_user_name(self) -> str:
        """Get the user's name from profile."""
        return self.user_profile.get_name()

    async def _maybe_compact(self, context: ConversationContext) -> None:
        """Run compaction if the context is too large."""
        from .compaction import compact_conversation, estimate_tokens

        estimated = estimate_tokens(context.messages)
        threshold = int(
            self.compaction_config.max_context_tokens
            * self.compaction_config.compaction_threshold
        )

        if estimated >= threshold:
            logger.info(
                "Context approaching limit, running compaction",
                estimated_tokens=estimated,
                threshold=threshold,
            )
            compacted_messages, result = await compact_conversation(
                self.llm,
                context.messages,
                self.compaction_config,
            )
            if result.success:
                context.messages = compacted_messages
                context.compaction_count += 1

    async def process_message(
        self,
        message: str,
        context: ConversationContext | None = None,
    ) -> tuple[str, ConversationContext]:
        """Process a user message and return a response.

        Includes:
        - Automatic conversation compaction when context is large
        - Exec-approval for dangerous tool calls
        - Tool execution loop with iteration limit
        """
        if context is None:
            context = ConversationContext(system_prompt=self.system_prompt)

        # Run compaction if needed before processing
        await self._maybe_compact(context)

        context.add_user_message(message)

        tools = self.tool_registry.get_definitions()

        iteration = 0
        response = None
        while iteration < self.max_tool_iterations:
            iteration += 1

            try:
                response = await self.llm.generate(
                    messages=context.messages,
                    tools=tools if tools else None,
                    system_prompt=context.system_prompt,
                )
            except Exception as e:
                logger.error("LLM generation error", error=str(e))
                error_msg = f"I encountered an error processing your message: {str(e)}"
                context.add_assistant_message(error_msg)
                return error_msg, context

            if response.tool_calls:
                context.add_assistant_message(response.content, response.tool_calls)

                for tool_call in response.tool_calls:
                    logger.info(
                        "Executing tool",
                        tool=tool_call.name,
                        arguments=tool_call.arguments,
                    )

                    # Check if this tool needs approval
                    from ..tools.exec_approval import get_approval_manager
                    approval_mgr = get_approval_manager()

                    if approval_mgr.needs_approval(tool_call.name):
                        # Create approval request - the tool won't execute yet
                        approval = approval_mgr.create_approval_request(
                            tool_call.name,
                            tool_call.arguments,
                        )
                        result_text = (
                            f"This action requires your approval before I can execute it.\n"
                            f"Approval ID: `{approval.id}`\n"
                            f"Use `/approve {approval.id}` to allow this action."
                        )
                        context.add_tool_result(tool_call.id, result_text, tool_call.name)
                        continue

                    result = await self.tool_registry.execute(
                        tool_call.name,
                        tool_call.arguments,
                    )

                    result_text = result.output if result.success else f"Error: {result.error}"
                    context.add_tool_result(tool_call.id, result_text, tool_call.name)

            else:
                context.add_assistant_message(response.content)
                context.truncate(self.settings.max_context_messages)
                return response.content, context

        timeout_msg = "I've reached the maximum number of tool iterations. Here's what I have so far."
        if response and response.content:
            timeout_msg = f"{response.content}\n\n{timeout_msg}"
        context.add_assistant_message(timeout_msg)
        return timeout_msg, context

    async def stream_message(
        self,
        message: str,
        context: ConversationContext | None = None,
    ) -> AsyncIterator[str]:
        """Stream a response to a user message."""
        if context is None:
            context = ConversationContext(system_prompt=self.system_prompt)

        context.add_user_message(message)

        try:
            full_response = ""
            async for chunk in self.llm.stream(
                messages=context.messages,
                system_prompt=context.system_prompt,
            ):
                full_response += chunk
                yield chunk

            context.add_assistant_message(full_response)

        except Exception as e:
            logger.error("LLM streaming error", error=str(e))
            yield f"Error: {str(e)}"
