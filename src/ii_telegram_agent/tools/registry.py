"""
Tool registry for managing available tools.
"""

from functools import lru_cache
from typing import Any, Union

import structlog

from ..config import get_settings
from ..llm.base import ToolDefinition
from .base import BaseTool, Tool, ToolResult

logger = structlog.get_logger()


class ToolRegistry:
    """Registry for managing tools."""
    
    def __init__(self):
        self._tools: dict[str, Union[BaseTool, Tool]] = {}
    
    def register(self, tool: Union[BaseTool, Tool]) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
        logger.info("Tool registered", tool_name=tool.name)
    
    def unregister(self, name: str) -> None:
        """Unregister a tool."""
        if name in self._tools:
            del self._tools[name]
            logger.info("Tool unregistered", tool_name=name)
    
    def get(self, name: str) -> Union[BaseTool, Tool, None]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())
    
    def get_definitions(self) -> list[ToolDefinition]:
        """Get all tool definitions for LLM."""
        definitions = []
        for tool in self._tools.values():
            if isinstance(tool, Tool):
                definitions.append(ToolDefinition(
                    name=tool.name,
                    description=tool.description,
                    parameters=tool.get_parameters_schema(),
                ))
            else:
                definitions.append(ToolDefinition(
                    name=tool.name,
                    description=tool.description,
                    parameters=tool.parameters,
                ))
        return definitions
    
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
    
    _register_scheduler_tools(registry)
    _register_file_tools(registry)
    _register_shell_tools(registry)
    _register_email_tools(registry, settings)
    _register_calendar_tools(registry, settings)


def _register_scheduler_tools(registry: ToolRegistry) -> None:
    """Register scheduler-related tools."""
    try:
        from .scheduler_tool import create_scheduler_tools
        for tool in create_scheduler_tools():
            registry.register(tool)
    except Exception as e:
        logger.warning("Failed to register scheduler tools", error=str(e))


def _register_file_tools(registry: ToolRegistry) -> None:
    """Register file operation tools."""
    try:
        from .file_tool import create_file_tools
        for tool in create_file_tools():
            registry.register(tool)
    except Exception as e:
        logger.warning("Failed to register file tools", error=str(e))


def _register_shell_tools(registry: ToolRegistry) -> None:
    """Register shell command tools."""
    try:
        from .shell_tool import create_shell_tools
        for tool in create_shell_tools():
            registry.register(tool)
    except Exception as e:
        logger.warning("Failed to register shell tools", error=str(e))


def _register_email_tools(registry: ToolRegistry, settings) -> None:
    """Register email tools if configured."""
    try:
        if getattr(settings, 'enable_email', True):
            from .email_tool import create_email_tools
            for tool in create_email_tools():
                registry.register(tool)
    except Exception as e:
        logger.warning("Failed to register email tools", error=str(e))


def _register_calendar_tools(registry: ToolRegistry, settings) -> None:
    """Register calendar tools if configured."""
    try:
        if getattr(settings, 'enable_calendar', True):
            from .calendar_tool import create_calendar_tools
            for tool in create_calendar_tools():
                registry.register(tool)
    except Exception as e:
        logger.warning("Failed to register calendar tools", error=str(e))