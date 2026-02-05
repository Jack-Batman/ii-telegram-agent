"""
Core agent implementation.
"""

from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import structlog

from ..config import Settings, get_settings
from ..llm import BaseLLM, LLMMessage, LLMResponse, ToolCall, create_llm
from ..tools import ToolRegistry, get_tool_registry

logger = structlog.get_logger()

DEFAULT_SYSTEM_PROMPT = """You are II-Agent, a helpful AI assistant running on the user's own hardware via Telegram.

You have access to powerful tools that help you accomplish tasks:
- **web_search**: Search the internet for current information
- **browse_webpage**: Visit and read web pages
- **execute_code**: Run Python code for calculations and data processing

Guidelines:
1. Be helpful, accurate, and concise
2. Use tools when you need current information or to perform calculations
3. Explain your reasoning when helpful
4. If you're unsure, say so and offer to search for information
5. Format responses clearly using Markdown (Telegram supports basic Markdown)

You're running on the user's personal device, so maintain their privacy and security."""


@dataclass
class ConversationContext:
    """Context for a conversation."""
    
    messages: list[LLMMessage] = field(default_factory=list)
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    model: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    
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
    
    def add_tool_result(self, tool_call_id: str, result: str) -> None:
        """Add a tool result."""
        self.messages.append(LLMMessage(
            role="tool",
            content=result,
            tool_call_id=tool_call_id,
        ))
    
    def truncate(self, max_messages: int = 50) -> None:
        """Truncate message history to keep context manageable."""
        if len(self.messages) > max_messages:
            self.messages = self.messages[-max_messages:]


class Agent:
    """Main agent class that processes messages and generates responses."""
    
    def __init__(
        self,
        llm: BaseLLM | None = None,
        tool_registry: ToolRegistry | None = None,
        settings: Settings | None = None,
        system_prompt: str | None = None,
    ):
        self.settings = settings or get_settings()
        self.llm = llm or create_llm(settings=self.settings)
        self.tool_registry = tool_registry or get_tool_registry()
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.max_tool_iterations = 10
    
    async def process_message(
        self,
        message: str,
        context: ConversationContext | None = None,
    ) -> tuple[str, ConversationContext]:
        """Process a user message and return a response."""
        if context is None:
            context = ConversationContext(system_prompt=self.system_prompt)
        
        context.add_user_message(message)
        
        tools = self.tool_registry.get_definitions()
        
        iteration = 0
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
                    
                    result = await self.tool_registry.execute(
                        tool_call.name,
                        tool_call.arguments,
                    )
                    
                    result_text = result.output if result.success else f"Error: {result.error}"
                    context.add_tool_result(tool_call.id, result_text)
            
            else:
                context.add_assistant_message(response.content)
                context.truncate(self.settings.max_context_messages)
                return response.content, context
        
        timeout_msg = "I've reached the maximum number of tool iterations. Here's what I have so far."
        if response.content:
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