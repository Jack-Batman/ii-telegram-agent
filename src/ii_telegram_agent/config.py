"""
Configuration management for II-Telegram-Agent

Uses pydantic-settings for environment variable parsing and validation.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMConfig(BaseSettings):
    """Configuration for a single LLM provider."""

    model_config = SettingsConfigDict(extra="ignore")

    provider: Literal["anthropic", "openai", "google", "openrouter"] = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    api_key: str = ""
    base_url: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.7


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_nested_delimiter="__",
    )

    # Application
    app_name: str = "II-Telegram-Agent"
    debug: bool = False
    log_level: str = "INFO"

    # Server
    host: str = "0.0.0.0"
    port: int = 8080
    workers: int = 1

    # Telegram
    telegram_bot_token: str = Field(default="", description="Telegram Bot API token")
    telegram_webhook_url: str = Field(default="", description="Public URL for webhook")
    telegram_webhook_secret: str = Field(default="", description="Webhook secret for validation")

    # LLM Providers (API Keys)
    anthropic_api_key: str = Field(default="", description="Anthropic API key for Claude")
    openai_api_key: str = Field(default="", description="OpenAI API key")
    google_api_key: str = Field(default="", description="Google AI API key for Gemini")
    openrouter_api_key: str = Field(default="", description="OpenRouter API key")

    # Default model settings
    default_provider: Literal["anthropic", "openai", "google", "openrouter"] = "anthropic"
    default_model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float = 0.7

    # Tools
    tavily_api_key: str = Field(default="", description="Tavily API key for web search")
    e2b_api_key: str = Field(default="", description="E2B API key for code sandboxes")
    browserless_api_key: str = Field(default="", description="Browserless API key")

    # Security
    admin_password: str = Field(default="changeme", description="Admin dashboard password")
    jwt_secret: str = Field(default="change-this-secret-in-production", description="JWT signing secret")
    allowed_users: str = Field(default="", description="Comma-separated Telegram user IDs or usernames")
    pairing_enabled: bool = Field(default=True, description="Enable pairing mode for new users")
    rate_limit_messages: int = Field(default=30, description="Max messages per minute per user")

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/agent.db",
        description="Database connection URL"
    )

    # Redis (optional, for rate limiting and caching)
    redis_url: str = Field(default="", description="Redis connection URL")

    # Session
    session_timeout_hours: int = Field(default=24, description="Session timeout in hours")
    max_context_messages: int = Field(default=50, description="Max messages to keep in context")

    # Features
    enable_web_search: bool = True
    enable_browser: bool = True
    enable_code_execution: bool = True
    enable_file_operations: bool = True
    enable_voice: bool = False
    enable_exec_approval: bool = True
    enable_heartbeat: bool = True

    # Voice settings
    tts_model: str = Field(default="tts-1", description="OpenAI TTS model")
    tts_voice: str = Field(default="nova", description="TTS voice name")

    # Heartbeat settings
    heartbeat_interval_minutes: int = Field(default=30, description="Heartbeat check interval")
    heartbeat_active_hours_start: int = Field(default=8, description="Heartbeat active hours start")
    heartbeat_active_hours_end: int = Field(default=22, description="Heartbeat active hours end")

    @field_validator("allowed_users", mode="before")
    @classmethod
    def parse_allowed_users(cls, v: str) -> str:
        return v.strip() if v else ""

    @property
    def allowed_users_list(self) -> list[str]:
        """Get list of allowed users."""
        if not self.allowed_users:
            return []
        return [u.strip() for u in self.allowed_users.split(",") if u.strip()]

    def get_llm_config(self, provider: str | None = None) -> LLMConfig:
        """Get LLM configuration for a provider."""
        provider = provider or self.default_provider

        api_key_map = {
            "anthropic": self.anthropic_api_key,
            "openai": self.openai_api_key,
            "google": self.google_api_key,
            "openrouter": self.openrouter_api_key,
        }

        model_map = {
            "anthropic": "claude-sonnet-4-20250514",
            "openai": "gpt-4o",
            "google": "gemini-2.5-flash",
            "openrouter": "anthropic/claude-sonnet-4",
        }

        base_url_map = {
            "anthropic": None,
            "openai": None,
            "google": None,
            "openrouter": "https://openrouter.ai/api/v1",
        }

        return LLMConfig(
            provider=provider,  # type: ignore
            model=model_map.get(provider, self.default_model),
            api_key=api_key_map.get(provider, ""),
            base_url=base_url_map.get(provider),
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()