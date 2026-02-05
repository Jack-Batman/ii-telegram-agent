"""
LLM factory for creating provider instances.
"""

from ..config import LLMConfig, Settings
from .base import BaseLLM
from .anthropic import AnthropicLLM
from .openai import OpenAILLM


def create_llm(config: LLMConfig | None = None, settings: Settings | None = None) -> BaseLLM:
    """Create an LLM instance based on configuration."""
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
    elif provider in ["openai", "openrouter"]:
        return OpenAILLM(
            api_key=config.api_key,
            model=config.model,
            base_url=config.base_url,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        )
    elif provider == "google":
        return OpenAILLM(
            api_key=config.api_key,
            model=config.model,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")