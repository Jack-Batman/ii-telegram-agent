"""
Tests for conversation compaction module.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from ii_telegram_agent.agent.compaction import (
    CompactionConfig,
    CompactionResult,
    estimate_tokens,
    compact_conversation,
    _classify_message_importance,
    _extract_key_facts,
    _fallback_summary,
)
from ii_telegram_agent.llm.base import LLMMessage, LLMResponse


def test_estimate_tokens_empty():
    """Test token estimation for empty messages."""
    assert estimate_tokens([]) == 0


def test_estimate_tokens_basic():
    """Test token estimation for basic messages."""
    messages = [
        LLMMessage(role="user", content="Hello, how are you?"),
        LLMMessage(role="assistant", content="I'm doing well, thanks!"),
    ]
    tokens = estimate_tokens(messages)
    assert tokens > 0
    assert tokens < 100  # Should be reasonable for short messages


def test_classify_message_importance_tool():
    """Test that tool messages are rated higher."""
    tool_msg = LLMMessage(role="tool", content="Search results here")
    normal_msg = LLMMessage(role="user", content="Hello")

    tool_score = _classify_message_importance(tool_msg)
    normal_score = _classify_message_importance(normal_msg)

    assert tool_score > normal_score


def test_classify_message_importance_important_content():
    """Test that messages with important markers score higher."""
    important_msg = LLMMessage(role="user", content="Remember my name is Alex and my email is alex@test.com")
    mundane_msg = LLMMessage(role="user", content="ok thanks")

    important_score = _classify_message_importance(important_msg)
    mundane_score = _classify_message_importance(mundane_msg)

    assert important_score > mundane_score


def test_extract_key_facts():
    """Test key fact extraction from messages."""
    messages = [
        LLMMessage(role="user", content="My name is Alex and I work at Google"),
        LLMMessage(role="assistant", content="Nice to meet you, Alex!"),
        LLMMessage(role="tool", content="Search results: Python 3.12 released"),
    ]

    facts = _extract_key_facts(messages)
    assert len(facts) > 0
    assert any("Alex" in f for f in facts)


def test_fallback_summary():
    """Test fallback summary generation."""
    messages = [
        LLMMessage(role="user", content="Tell me about Python"),
        LLMMessage(role="assistant", content="Python is a programming language"),
        LLMMessage(role="user", content="What version is latest?"),
    ]
    key_facts = ["User interested in Python"]

    summary = _fallback_summary(messages, key_facts)
    assert "Python" in summary
    assert "Earlier" in summary or "user messages" in summary


@pytest.mark.asyncio
async def test_compact_conversation_no_compaction_needed():
    """Test that compaction is skipped when context is small."""
    mock_llm = MagicMock()
    messages = [
        LLMMessage(role="user", content="Hello"),
        LLMMessage(role="assistant", content="Hi there!"),
    ]

    config = CompactionConfig(max_context_tokens=100_000)
    compacted, result = await compact_conversation(mock_llm, messages, config)

    assert result.success
    assert result.tokens_saved_estimate == 0
    assert len(compacted) == len(messages)


@pytest.mark.asyncio
async def test_compact_conversation_disabled():
    """Test that compaction can be disabled."""
    mock_llm = MagicMock()
    messages = [LLMMessage(role="user", content="x" * 1000) for _ in range(100)]

    config = CompactionConfig(enabled=False)
    compacted, result = await compact_conversation(mock_llm, messages, config)

    assert result.success
    assert len(compacted) == len(messages)


def test_compaction_config_defaults():
    """Test CompactionConfig default values."""
    config = CompactionConfig()
    assert config.max_context_tokens == 100_000
    assert config.compaction_threshold == 0.7
    assert config.keep_recent_messages == 10
    assert config.preserve_tool_results is True
    assert config.enabled is True
