"""
OpenAI GPT LLM provider (also works with OpenRouter and compatible APIs).
"""

import json
from typing import Any, AsyncIterator

import openai
import structlog

from .base import BaseLLM, LLMMessage, LLMResponse, ToolCall, ToolDefinition

logger = structlog.get_logger()


class OpenAILLM(BaseLLM):
    """OpenAI GPT LLM provider."""
    
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        base_url: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        super().__init__(api_key, model, base_url, max_tokens, temperature)
        self.client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )
    
    @property
    def provider_name(self) -> str:
        return "openai"
    
    def _convert_messages(self, messages: list[LLMMessage]) -> list[dict[str, Any]]:
        """Convert LLMMessages to OpenAI format."""
        converted = []
        
        for msg in messages:
            if msg.role == "tool":
                converted.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content,
                })
            elif msg.role == "assistant" and msg.tool_calls:
                tool_calls = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in msg.tool_calls
                ]
                converted.append({
                    "role": "assistant",
                    "content": msg.content or None,
                    "tool_calls": tool_calls,
                })
            else:
                converted.append({
                    "role": msg.role,
                    "content": msg.content,
                })
        
        return converted
    
    def _convert_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        """Convert ToolDefinitions to OpenAI format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in tools
        ]
    
    async def generate(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Generate a response from GPT."""
        converted_messages = self._convert_messages(messages)
        
        if system_prompt:
            converted_messages.insert(0, {"role": "system", "content": system_prompt})
        
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": converted_messages,
        }
        
        if tools:
            kwargs["tools"] = self._convert_tools(tools)
        
        try:
            response = await self.client.chat.completions.create(**kwargs)
            
            choice = response.choices[0]
            message = choice.message
            
            content = message.content or ""
            tool_calls = []
            
            if message.tool_calls:
                for tc in message.tool_calls:
                    tool_calls.append(ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=json.loads(tc.function.arguments) if tc.function.arguments else {},
                    ))
            
            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                input_tokens=response.usage.prompt_tokens if response.usage else 0,
                output_tokens=response.usage.completion_tokens if response.usage else 0,
                model=response.model,
                stop_reason=choice.finish_reason,
                raw_response=response,
            )
        
        except openai.APIError as e:
            logger.error("OpenAI API error", error=str(e))
            raise
    
    async def stream(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        """Stream a response from GPT."""
        converted_messages = self._convert_messages(messages)
        
        if system_prompt:
            converted_messages.insert(0, {"role": "system", "content": system_prompt})
        
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": converted_messages,
            "stream": True,
        }
        
        if tools:
            kwargs["tools"] = self._convert_tools(tools)
        
        try:
            stream = await self.client.chat.completions.create(**kwargs)
            
            async for chunk in stream:  # type: ignore
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        
        except openai.APIError as e:
            logger.error("OpenAI streaming error", error=str(e))
            raise