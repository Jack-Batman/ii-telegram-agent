"""
LLM factory for creating provider instances.

Supports: Anthropic Claude, OpenAI GPT, Google Gemini (native), OpenRouter.
"""

from ..config import LLMConfig, Settings
from .base import BaseLLM
from .anthropic import AnthropicLLM
from .openai import OpenAILLM


def create_llm(config: LLMConfig | None = None, settings: Settings | None = None) -> BaseLLM:
    """Create an LLM instance based on configuration.

    Provider routing:
    - anthropic -> AnthropicLLM (native Anthropic SDK)
    - openai -> OpenAILLM (native OpenAI SDK)
    - google -> GoogleGeminiLLM (native Gemini SDK)
    - openrouter -> OpenAILLM (OpenAI-compatible endpoint)
    """
    if config is None:
        if settings is None:
            from ..config import get_settings
            settings = get_settings()
        config = settings.get_llm_config()

    provider = config.provider

    if provider == "anthropic":
        return AnthropicLLM(
            api_key=config.api_key,
            model=config.model,
            base_url=config.base_url,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        )
    elif provider == "openai":
        return OpenAILLM(
            api_key=config.api_key,
            model=config.model,
            base_url=config.base_url,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        )
    elif provider == "google":
        # Use native Gemini SDK for full feature support
        try:
            from .google import GoogleGeminiLLM
            return GoogleGeminiLLM(
                api_key=config.api_key,
                model=config.model,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
            )
        except ImportError:
            # Fall back to OpenAI-compatible endpoint
            import structlog
            logger = structlog.get_logger()
            logger.warning(
                "google-generativeai not installed, using OpenAI-compatible shim for Gemini"
            )
            return OpenAILLM(
                api_key=config.api_key,
                model=config.model,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                max_tokens=config.max_tokens,
                temperature=config.temperature,
            )
    elif provider == "openrouter":
        return OpenAILLM(
            api_key=config.api_key,
            model=config.model,
            base_url=config.base_url or "https://openrouter.ai/api/v1",
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
