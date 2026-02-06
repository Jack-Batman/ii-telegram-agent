"""
LLM module for multi-provider AI model support.

Providers:
- Anthropic Claude (native SDK)
- OpenAI GPT (native SDK)
- Google Gemini (native SDK with OpenAI-compatible fallback)
- OpenRouter (via OpenAI-compatible endpoint)
"""

from .base import BaseLLM, LLMMessage, LLMResponse, ToolCall, ToolDefinition
from .anthropic import AnthropicLLM
from .openai import OpenAILLM
from .factory import create_llm

# Google provider imported lazily to avoid hard dependency
try:
    from .google import GoogleGeminiLLM
except ImportError:
    GoogleGeminiLLM = None  # type: ignore

__all__ = [
    "BaseLLM",
    "LLMMessage",
    "LLMResponse",
    "ToolCall",
    "ToolDefinition",
    "AnthropicLLM",
    "OpenAILLM",
    "GoogleGeminiLLM",
    "create_llm",
]