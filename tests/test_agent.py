"""
Tests for agent module.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ii_telegram_agent.agent.core import Agent, ConversationContext
from ii_telegram_agent.llm.base import LLMMessage, LLMResponse


def test_conversation_context_add_user_message():
    """Test adding user message to context."""
    context = ConversationContext()
    context.add_user_message("Hello!")
    
    assert len(context.messages) == 1
    assert context.messages[0].role == "user"
    assert context.messages[0].content == "Hello!"


def test_conversation_context_add_assistant_message():
    """Test adding assistant message to context."""
    context = ConversationContext()
    context.add_assistant_message("Hi there!")
    
    assert len(context.messages) == 1
    assert context.messages[0].role == "assistant"
    assert context.messages[0].content == "Hi there!"


def test_conversation_context_truncate():
    """Test truncating conversation context."""
    context = ConversationContext()
    
    for i in range(100):
        context.add_user_message(f"Message {i}")
    
    assert len(context.messages) == 100
    
    context.truncate(max_messages=10)
    
    assert len(context.messages) == 10
    assert context.messages[0].content == "Message 90"


def test_conversation_context_tool_result():
    """Test adding tool result to context."""
    context = ConversationContext()
    context.add_tool_result("tool_123", "Result data")
    
    assert len(context.messages) == 1
    assert context.messages[0].role == "tool"
    assert context.messages[0].tool_call_id == "tool_123"
    assert context.messages[0].content == "Result data"


@pytest.mark.asyncio
async def test_agent_process_message():
    """Test agent processing a message."""
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=LLMResponse(
        content="Hello! How can I help you?",
        tool_calls=[],
        input_tokens=10,
        output_tokens=20,
    ))
    mock_llm.model = "test-model"
    
    mock_registry = MagicMock()
    mock_registry.get_definitions.return_value = []
    
    agent = Agent(llm=mock_llm, tool_registry=mock_registry)
    
    response, context = await agent.process_message("Hello!")
    
    assert response == "Hello! How can I help you?"
    assert len(context.messages) == 2
    assert context.messages[0].role == "user"
    assert context.messages[1].role == "assistant"


@pytest.mark.asyncio
async def test_agent_handles_error():
    """Test agent handles LLM errors gracefully."""
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(side_effect=Exception("API Error"))
    mock_llm.model = "test-model"
    
    mock_registry = MagicMock()
    mock_registry.get_definitions.return_value = []
    
    agent = Agent(llm=mock_llm, tool_registry=mock_registry)
    
    response, context = await agent.process_message("Hello!")
    
    assert "error" in response.lower()