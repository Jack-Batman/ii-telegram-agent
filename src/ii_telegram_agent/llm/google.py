"""
Native Google Gemini LLM provider.

Uses the google-generativeai SDK directly instead of routing through
the OpenAI-compatible shim, giving access to Gemini-specific features
like grounding, safety settings, and native function calling.
"""

import json
from typing import Any, AsyncIterator

import structlog

from .base import BaseLLM, LLMMessage, LLMResponse, ToolCall, ToolDefinition

logger = structlog.get_logger()


class GoogleGeminiLLM(BaseLLM):
    """Native Google Gemini LLM provider."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        base_url: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        super().__init__(api_key, model, base_url, max_tokens, temperature)
        self._client = None

    def _get_client(self):
        """Lazy-initialize the Gemini client."""
        if self._client is None:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._client = genai
            except ImportError:
                raise ImportError(
                    "google-generativeai not installed. "
                    "Run: pip install google-generativeai"
                )
        return self._client

    @property
    def provider_name(self) -> str:
        return "google"

    def _convert_messages(self, messages: list[LLMMessage]) -> list[dict[str, Any]]:
        """Convert LLMMessages to Gemini format.

        Gemini uses 'user' and 'model' roles, and has a different
        structure for tool calls/results.
        """
        converted = []

        for msg in messages:
            if msg.role == "system":
                continue  # System prompt handled separately

            if msg.role == "tool":
                converted.append({
                    "role": "user",
                    "parts": [{
                        "function_response": {
                            "name": msg.name or "unknown",
                            "response": {"result": msg.content},
                        }
                    }],
                })
            elif msg.role == "assistant":
                parts = []
                if msg.content:
                    parts.append({"text": msg.content})
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        parts.append({
                            "function_call": {
                                "name": tc.name,
                                "args": tc.arguments,
                            }
                        })
                converted.append({"role": "model", "parts": parts})
            elif msg.role == "user":
                converted.append({
                    "role": "user",
                    "parts": [{"text": msg.content}],
                })

        return converted

    def _convert_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        """Convert ToolDefinitions to Gemini function declarations."""
        function_declarations = []

        for tool in tools:
            # Gemini expects a slightly different schema format
            params = dict(tool.parameters)
            # Remove 'required' from top-level if present (Gemini handles it differently)
            required = params.pop("required", [])

            # Add required flag to individual properties
            properties = params.get("properties", {})
            for prop_name, prop_def in properties.items():
                if prop_name in required:
                    prop_def["required"] = True

            function_declarations.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": params,
            })

        return [{"function_declarations": function_declarations}]

    async def generate(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Generate a response from Gemini."""
        genai = self._get_client()

        generation_config = {
            "max_output_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

        model_kwargs: dict[str, Any] = {
            "model_name": self.model,
            "generation_config": generation_config,
        }

        if system_prompt:
            model_kwargs["system_instruction"] = system_prompt

        model = genai.GenerativeModel(**model_kwargs)

        converted_messages = self._convert_messages(messages)

        generate_kwargs: dict[str, Any] = {
            "contents": converted_messages,
        }

        if tools:
            generate_kwargs["tools"] = self._convert_tools(tools)

        try:
            response = await model.generate_content_async(**generate_kwargs)

            content = ""
            tool_calls = []

            if response.candidates:
                candidate = response.candidates[0]
                for part in candidate.content.parts:
                    if hasattr(part, "text") and part.text:
                        content += part.text
                    elif hasattr(part, "function_call") and part.function_call:
                        fc = part.function_call
                        tool_calls.append(ToolCall(
                            id=f"gemini_{fc.name}_{len(tool_calls)}",
                            name=fc.name,
                            arguments=dict(fc.args) if fc.args else {},
                        ))

            # Extract token usage if available
            input_tokens = 0
            output_tokens = 0
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0)
                output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0)

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=self.model,
                stop_reason=candidate.finish_reason.name if response.candidates else None,
                raw_response=response,
            )

        except Exception as e:
            logger.error("Gemini API error", error=str(e))
            raise

    async def stream(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        """Stream a response from Gemini."""
        genai = self._get_client()

        generation_config = {
            "max_output_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

        model_kwargs: dict[str, Any] = {
            "model_name": self.model,
            "generation_config": generation_config,
        }

        if system_prompt:
            model_kwargs["system_instruction"] = system_prompt

        model = genai.GenerativeModel(**model_kwargs)

        converted_messages = self._convert_messages(messages)

        try:
            response = await model.generate_content_async(
                contents=converted_messages,
                stream=True,
            )

            async for chunk in response:
                if chunk.text:
                    yield chunk.text

        except Exception as e:
            logger.error("Gemini streaming error", error=str(e))
            raise
