"""
Memory Manager - Persistent long-term memory for the agent.

This module handles reading, writing, and updating the MEMORY.md file
which stores important information across sessions.
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages persistent memory stored in MEMORY.md."""
    
    def __init__(self, workspace_dir: Optional[str] = None):
        """Initialize the memory manager.
        
        Args:
            workspace_dir: Path to the workspace directory containing MEMORY.md
        """
        self.workspace_dir = Path(workspace_dir or os.getenv("WORKSPACE_DIR", "~/.ii-telegram-agent/workspace"))
        self.workspace_dir = self.workspace_dir.expanduser()
        self.memory_file = self.workspace_dir / "MEMORY.md"
        self._ensure_memory_file()
    
    def _ensure_memory_file(self):
        """Ensure the memory file exists with default structure."""
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        
        if not self.memory_file.exists():
            default_content = """# Long-Term Memory

This file stores important information that should be remembered across conversations.

## User Preferences
<!-- Automatically updated based on conversations -->

## Important Facts
<!-- Key information the user has shared -->

## Ongoing Projects
<!-- Projects the user is working on -->

## Reminders & Notes
<!-- Things to remember -->

---
*Last updated: {date}*
""".format(date=datetime.now().strftime("%Y-%m-%d %H:%M"))
            
            self.memory_file.write_text(default_content)
            logger.info(f"Created memory file at {self.memory_file}")
    
    def read(self) -> str:
        """Read the entire memory file.
        
        Returns:
            The contents of MEMORY.md
        """
        try:
            return self.memory_file.read_text()
        except Exception as e:
            logger.error(f"Error reading memory file: {e}")
            return ""
    
    def get_section(self, section_name: str) -> str:
        """Get the content of a specific section.
        
        Args:
            section_name: Name of the section (e.g., "User Preferences")
            
        Returns:
            Content of the section
        """
        content = self.read()
        pattern = rf"## {re.escape(section_name)}\n(.*?)(?=\n## |\n---|\Z)"
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            return match.group(1).strip()
        return ""
    
    def update_section(self, section_name: str, new_content: str):
        """Update a specific section in the memory file.
        
        Args:
            section_name: Name of the section to update
            new_content: New content for the section
        """
        content = self.read()
        pattern = rf"(## {re.escape(section_name)}\n)(.*?)(?=\n## |\n---|\Z)"
        
        def replace_section(match):
            return f"{match.group(1)}{new_content}\n\n"
        
        new_memory = re.sub(pattern, replace_section, content, flags=re.DOTALL)
        
        # Update timestamp
        new_memory = re.sub(
            r"\*Last updated:.*?\*",
            f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
            new_memory
        )
        
        self.memory_file.write_text(new_memory)
        logger.info(f"Updated section '{section_name}' in memory")
    
    def add_memory(self, section_name: str, memory: str):
        """Add a new memory entry to a section.
        
        Args:
            section_name: Name of the section
            memory: Memory to add
        """
        current = self.get_section(section_name)
        timestamp = datetime.now().strftime("%Y-%m-%d")
        
        # Remove HTML comments if present
        current = re.sub(r"<!--.*?-->", "", current).strip()
        
        new_entry = f"- [{timestamp}] {memory}"
        
        if current:
            new_content = f"{current}\n{new_entry}"
        else:
            new_content = new_entry
        
        self.update_section(section_name, new_content)
    
    def add_preference(self, preference: str):
        """Add a user preference to memory."""
        self.add_memory("User Preferences", preference)
    
    def add_fact(self, fact: str):
        """Add an important fact to memory."""
        self.add_memory("Important Facts", fact)
    
    def add_project(self, project: str):
        """Add an ongoing project to memory."""
        self.add_memory("Ongoing Projects", project)
    
    def add_reminder(self, reminder: str):
        """Add a reminder to memory."""
        self.add_memory("Reminders & Notes", reminder)
    
    def search(self, query: str) -> list[str]:
        """Search memory for entries matching a query.
        
        Args:
            query: Search query
            
        Returns:
            List of matching memory entries
        """
        content = self.read()
        query_lower = query.lower()
        matches = []
        
        for line in content.split("\n"):
            if query_lower in line.lower() and line.strip().startswith("-"):
                matches.append(line.strip())
        
        return matches
    
    def get_recent_memories(self, limit: int = 10) -> list[str]:
        """Get the most recent memory entries.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of recent memory entries
        """
        content = self.read()
        entries = []
        
        # Extract dated entries
        pattern = r"- \[(\d{4}-\d{2}-\d{2})\] (.+)"
        for match in re.finditer(pattern, content):
            entries.append((match.group(1), match.group(2)))
        
        # Sort by date descending
        entries.sort(key=lambda x: x[0], reverse=True)
        
        return [f"[{date}] {text}" for date, text in entries[:limit]]
    
    def clear_section(self, section_name: str):
        """Clear all entries in a section.
        
        Args:
            section_name: Name of the section to clear
        """
        self.update_section(section_name, "<!-- Section cleared -->")
    
    def get_context_for_prompt(self) -> str:
        """Get a formatted memory context for inclusion in prompts.
        
        Returns:
            Formatted memory context string
        """
        recent = self.get_recent_memories(5)
        preferences = self.get_section("User Preferences")
        facts = self.get_section("Important Facts")
        projects = self.get_section("Ongoing Projects")
        
        context_parts = []
        
        if preferences and not preferences.startswith("<!--"):
            context_parts.append(f"**User Preferences:**\n{preferences}")
        
        if facts and not facts.startswith("<!--"):
            context_parts.append(f"**Important Facts:**\n{facts}")
        
        if projects and not projects.startswith("<!--"):
            context_parts.append(f"**Current Projects:**\n{projects}")
        
        if recent:
            context_parts.append(f"**Recent Memories:**\n" + "\n".join(f"- {m}" for m in recent))
        
        if context_parts:
            return "\n\n".join(context_parts)
        
        return "No memories stored yet."