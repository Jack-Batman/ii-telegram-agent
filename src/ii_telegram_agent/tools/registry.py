"""
Tool registry for managing available tools.
"""

from functools import lru_cache
from typing import Any

import structlog

from ..config import get_settings
from ..llm.base import ToolDefinition
from .base import BaseTool, ToolResult

logger = structlog.get_logger()


class ToolRegistry:
    """Registry for managing tools."""
    
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
    
    def register(self, tool: BaseTool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
        logger.info("Tool registered", tool_name=tool.name)
    
    def unregister(self, name: str) -> None:
        """Unregister a tool."""
        if name in self._tools:
            del self._tools[name]
            logger.info("Tool unregistered", tool_name=name)
    
    def get(self, name: str) -> BaseTool | None:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())
    
    def get_definitions(self) -> list[ToolDefinition]:
        """Get all tool definitions for LLM."""
        return [
            ToolDefinition(
                name=tool.name,
                description=tool.description,
                parameters=tool.parameters,
            )
            for tool in self._tools.values()
        ]
    
    async def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Execute a tool by name."""
        tool = self.get(name)
        if tool is None:
            return ToolResult(
                success=False,
                output="",
                error=f"Tool '{name}' not found",
            )
        
        try:
            logger.info("Executing tool", tool_name=name, arguments=arguments)
            result = await tool.execute(**arguments)
            logger.info("Tool executed", tool_name=name, success=result.success)
            return result
        except Exception as e:
            logger.error("Tool execution error", tool_name=name, error=str(e))
            return ToolResult(
                success=False,
                output="",
                error=str(e),
            )


_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Get or create the global tool registry."""
    global _registry
    
    if _registry is None:
        _registry = ToolRegistry()
        _initialize_default_tools(_registry)
    
    return _registry


def _initialize_default_tools(registry: ToolRegistry) -> None:
    """Initialize default tools based on settings."""
    settings = get_settings()
    
    if settings.enable_web_search:
        from .web_search import WebSearchTool
        registry.register(WebSearchTool(tavily_api_key=settings.tavily_api_key))
    
    if settings.enable_browser:
        from .browser import BrowserTool
        registry.register(BrowserTool())
    
    if settings.enable_code_execution:
        from .code_executor import CodeExecutorTool
        registry.register(CodeExecutorTool(e2b_api_key=settings.e2b_api_key))