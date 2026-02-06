"""
Agent module - the brain of the system.

Includes:
- Agent: Core message processing with LLM + tools
- SessionManager: Persistent conversation sessions
- ConversationContext: In-memory conversation state
- Compaction: Adaptive context summarization
"""

from .core import Agent, ConversationContext
from .session import SessionManager
from .compaction import CompactionConfig, compact_conversation

__all__ = [
    "Agent",
    "ConversationContext",
    "SessionManager",
    "CompactionConfig",
    "compact_conversation",
]