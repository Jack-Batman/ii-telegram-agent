"""
Tests for configuration module.
"""

import os
from unittest.mock import patch

import pytest

from ii_telegram_agent.config import Settings, LLMConfig


def test_settings_default_values():
    """Test that settings have sensible defaults."""
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings()
        
        assert settings.app_name == "II-Telegram-Agent"
        assert settings.port == 8080
        assert settings.default_provider == "anthropic"
        assert settings.pairing_enabled is True
        assert settings.rate_limit_messages == 30


def test_settings_from_env():
    """Test loading settings from environment variables."""
    env = {
        "TELEGRAM_BOT_TOKEN": "test_token",
        "ANTHROPIC_API_KEY": "test_anthropic_key",
        "DEFAULT_MODEL": "claude-opus-4",
        "PAIRING_ENABLED": "false",
    }
    
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()
        
        assert settings.telegram_bot_token == "test_token"
        assert settings.anthropic_api_key == "test_anthropic_key"
        assert settings.default_model == "claude-opus-4"
        assert settings.pairing_enabled is False


def test_allowed_users_list():
    """Test parsing allowed users list."""
    env = {"ALLOWED_USERS": "123456,789012,testuser"}
    
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()
        
        assert settings.allowed_users_list == ["123456", "789012", "testuser"]


def test_allowed_users_empty():
    """Test empty allowed users list."""
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings()
        
        assert settings.allowed_users_list == []


def test_get_llm_config():
    """Test getting LLM configuration."""
    env = {
        "ANTHROPIC_API_KEY": "test_key",
        "DEFAULT_PROVIDER": "anthropic",
    }
    
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()
        config = settings.get_llm_config()
        
        assert config.provider == "anthropic"
        assert config.api_key == "test_key"
        assert "claude" in config.model.lower()


def test_get_llm_config_openai():
    """Test getting OpenAI LLM configuration."""
    env = {
        "OPENAI_API_KEY": "test_openai_key",
    }
    
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()
        config = settings.get_llm_config("openai")
        
        assert config.provider == "openai"
        assert config.api_key == "test_openai_key"
        assert "gpt" in config.model.lower()