"""
Anthropic Claude LLM provider.
"""

import json
from typing import Any, AsyncIterator

import anthropic
import structlog

from .base import BaseLLM, LLMMessage, LLMResponse, ToolCall, ToolDefinition

logger = structlog.get_logger()


class AnthropicLLM(BaseLLM):
    """Anthropic Claude LLM provider."""
    
    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        base_url: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        super().__init__(api_key, model, base_url, max_tokens, temperature)
        self.client = anthropic.AsyncAnthropic(
            api_key=api_key,
            base_url=base_url,
        )
    
    @property
    def provider_name(self) -> str:
        return "anthropic"
    
    def _convert_messages(self, messages: list[LLMMessage]) -> list[dict[str, Any]]:
        """Convert LLMMessages to Anthropic format."""
        converted = []
        
        for msg in messages:
            if msg.role == "system":
                continue
            
            if msg.role == "tool":
                converted.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.tool_call_id,
                            "content": msg.content,
                        }
                    ],
                })
            elif msg.role == "assistant" and msg.tool_calls:
                content: list[dict[str, Any]] = []
                if msg.content:
                    content.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    content.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    })
                converted.append({"role": "assistant", "content": content})
            else:
                converted.append({
                    "role": msg.role,
                    "content": msg.content,
                })
        
        return converted
    
    def _convert_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        """Convert ToolDefinitions to Anthropic format."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters,
            }
            for tool in tools
        ]
    
    def _extract_system_prompt(self, messages: list[LLMMessage]) -> str | None:
        """Extract system prompt from messages."""
        for msg in messages:
            if msg.role == "system":
                return msg.content
        return None
    
    async def generate(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Generate a response from Claude."""
        system = system_prompt or self._extract_system_prompt(messages)
        converted_messages = self._convert_messages(messages)
        
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": converted_messages,
        }
        
        if system:
            kwargs["system"] = system
        
        if tools:
            kwargs["tools"] = self._convert_tools(tools)
        
        try:
            response = await self.client.messages.create(**kwargs)
            
            content = ""
            tool_calls = []
            
            for block in response.content:
                if block.type == "text":
                    content += block.text
                elif block.type == "tool_use":
                    tool_calls.append(ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=dict(block.input) if isinstance(block.input, dict) else {},
                    ))
            
            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                model=response.model,
                stop_reason=response.stop_reason,
                raw_response=response,
            )
        
        except anthropic.APIError as e:
            logger.error("Anthropic API error", error=str(e))
            raise
    
    async def stream(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        """Stream a response from Claude."""
        system = system_prompt or self._extract_system_prompt(messages)
        converted_messages = self._convert_messages(messages)
        
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": converted_messages,
        }
        
        if system:
            kwargs["system"] = system
        
        if tools:
            kwargs["tools"] = self._convert_tools(tools)
        
        try:
            async with self.client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text
        
        except anthropic.APIError as e:
            logger.error("Anthropic streaming error", error=str(e))
            raise