"""
Base classes for tools.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Optional


@dataclass
class ToolResult:
    """Result from a tool execution."""
    
    success: bool
    output: str = ""
    data: Any = None
    error: str | None = None


@dataclass
class ToolParameter:
    """Definition of a tool parameter."""
    
    name: str
    param_type: str  # string, integer, boolean, array, object
    description: str
    required: bool = True
    default: Any = None
    enum: list[str] | None = None


@dataclass
class Tool:
    """
    Simple tool wrapper that can be created from a function.
    
    This is an alternative to the class-based BaseTool for simpler tools.
    """
    
    name: str
    description: str
    parameters: list[ToolParameter]
    handler: Callable[..., Coroutine[Any, Any, ToolResult]]
    
    def get_parameters_schema(self) -> dict[str, Any]:
        """Convert parameters to JSON Schema format."""
        properties = {}
        required = []
        
        for param in self.parameters:
            prop = {
                "type": param.param_type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            if param.default is not None:
                prop["default"] = param.default
            
            properties[param.name] = prop
            
            if param.required:
                required.append(param.name)
        
        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }
    
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool handler."""
        return await self.handler(**kwargs)


class BaseTool(ABC):
    """Base class for all tools."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Get the tool name."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Get the tool description."""
        pass
    
    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """Get the tool parameters schema (JSON Schema)."""
        pass
    
    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with given arguments."""
        pass
    
    def to_definition(self) -> dict[str, Any]:
        """Convert to a tool definition for LLM."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }