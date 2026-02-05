"""
Base classes for tools.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolResult:
    """Result from a tool execution."""
    
    success: bool
    output: str
    data: Any = None
    error: str | None = None


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