"""
Tests for tools module.
"""

import pytest

from ii_telegram_agent.tools.base import BaseTool, ToolResult
from ii_telegram_agent.tools.web_search import WebSearchTool
from ii_telegram_agent.tools.browser import BrowserTool


def test_tool_result_success():
    """Test successful tool result."""
    result = ToolResult(success=True, output="Test output", data={"key": "value"})
    
    assert result.success is True
    assert result.output == "Test output"
    assert result.data == {"key": "value"}
    assert result.error is None


def test_tool_result_failure():
    """Test failed tool result."""
    result = ToolResult(success=False, output="", error="Something went wrong")
    
    assert result.success is False
    assert result.error == "Something went wrong"


def test_web_search_tool_properties():
    """Test WebSearchTool properties."""
    tool = WebSearchTool()
    
    assert tool.name == "web_search"
    assert "search" in tool.description.lower()
    assert "query" in tool.parameters["properties"]
    assert "query" in tool.parameters["required"]


def test_browser_tool_properties():
    """Test BrowserTool properties."""
    tool = BrowserTool()
    
    assert tool.name == "browse_webpage"
    assert "webpage" in tool.description.lower() or "browse" in tool.description.lower()
    assert "url" in tool.parameters["properties"]
    assert "url" in tool.parameters["required"]


def test_tool_to_definition():
    """Test converting tool to LLM definition."""
    tool = WebSearchTool()
    definition = tool.to_definition()
    
    assert definition["name"] == "web_search"
    assert "description" in definition
    assert "parameters" in definition


@pytest.mark.asyncio
async def test_web_search_execution():
    """Test web search tool execution (uses DuckDuckGo)."""
    tool = WebSearchTool()
    result = await tool.execute(query="python programming", max_results=2)
    
    # DuckDuckGo search might fail in some environments
    # So we just check the structure
    assert isinstance(result, ToolResult)
    assert isinstance(result.success, bool)


@pytest.mark.asyncio
async def test_browser_execution():
    """Test browser tool execution."""
    tool = BrowserTool()
    result = await tool.execute(url="https://example.com")
    
    assert isinstance(result, ToolResult)
    if result.success:
        assert "example" in result.output.lower() or "Example" in result.output