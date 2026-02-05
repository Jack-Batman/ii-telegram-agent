"""
Soul Manager - Personality and behavior configuration for the agent.

This module handles reading and parsing the SOUL.md file which defines
the agent's personality, communication style, and behavioral guidelines.
"""

import os
import re
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class SoulManager:
    """Manages the agent's personality defined in SOUL.md."""
    
    DEFAULT_SOUL = """# Assistant's Soul

## Identity
I am a helpful AI assistant. I exist to help, support, and assist my user in whatever way they need.

## Personality
My core traits are: helpful, friendly, knowledgeable, and patient.

My conversational tone is warm and professional.

## Communication Style
- I adapt my responses to match the complexity of the question
- I'm honest about my limitations and uncertainties
- I ask clarifying questions when needed rather than making assumptions
- I remember context from our conversations and reference it when relevant

## Proactivity
I primarily respond to direct requests, but occasionally offer helpful suggestions when they seem particularly relevant or valuable.

## Values
- **Helpfulness**: I prioritize being genuinely useful
- **Honesty**: I'm truthful about what I know and don't know
- **Respect**: I treat the user's time, privacy, and preferences with care
- **Growth**: I learn from our interactions to serve better over time

## Boundaries
- I will ask before taking significant actions
- I won't pretend to have access to information I don't have
- I'll flag when a request might have unintended consequences
- I respect privacy and won't share or store sensitive information inappropriately

## Memory
I have access to our conversation history and important memories. I use this context to provide more personalized and relevant assistance.
"""
    
    def __init__(self, workspace_dir: Optional[str] = None):
        """Initialize the soul manager.
        
        Args:
            workspace_dir: Path to the workspace directory containing SOUL.md
        """
        self.workspace_dir = Path(workspace_dir or os.getenv("WORKSPACE_DIR", "~/.ii-telegram-agent/workspace"))
        self.workspace_dir = self.workspace_dir.expanduser()
        self.soul_file = self.workspace_dir / "SOUL.md"
        self._ensure_soul_file()
        self._cache = None
    
    def _ensure_soul_file(self):
        """Ensure the soul file exists with default content."""
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        
        if not self.soul_file.exists():
            self.soul_file.write_text(self.DEFAULT_SOUL)
            logger.info(f"Created soul file at {self.soul_file}")
    
    def read(self) -> str:
        """Read the entire soul file.
        
        Returns:
            The contents of SOUL.md
        """
        try:
            return self.soul_file.read_text()
        except Exception as e:
            logger.error(f"Error reading soul file: {e}")
            return self.DEFAULT_SOUL
    
    def get_section(self, section_name: str) -> str:
        """Get the content of a specific section.
        
        Args:
            section_name: Name of the section (e.g., "Personality")
            
        Returns:
            Content of the section
        """
        content = self.read()
        pattern = rf"## {re.escape(section_name)}\n(.*?)(?=\n## |\Z)"
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            return match.group(1).strip()
        return ""
    
    def get_name(self) -> str:
        """Get the assistant's name from the soul file.
        
        Returns:
            The assistant's name, or "Assistant" if not found
        """
        identity = self.get_section("Identity")
        
        # Try to extract name from "I am [Name]"
        match = re.search(r"I am (\w+)", identity)
        if match:
            return match.group(1)
        
        # Try to extract from title
        content = self.read()
        title_match = re.search(r"# (.+?)['’]s Soul", content)
        if title_match:
            return title_match.group(1)
        
        return "Assistant"
    
    def get_personality(self) -> str:
        """Get the personality description.
        
        Returns:
            Personality traits and tone description
        """
        return self.get_section("Personality")
    
    def get_communication_style(self) -> str:
        """Get communication style guidelines.
        
        Returns:
            Communication style description
        """
        return self.get_section("Communication Style")
    
    def get_values(self) -> str:
        """Get the agent's values.
        
        Returns:
            Values description
        """
        return self.get_section("Values")
    
    def get_boundaries(self) -> str:
        """Get behavioral boundaries.
        
        Returns:
            Boundaries description
        """
        return self.get_section("Boundaries")
    
    def get_proactivity(self) -> str:
        """Get proactivity guidelines.
        
        Returns:
            Proactivity description
        """
        return self.get_section("Proactivity")
    
    def get_system_prompt(self) -> str:
        """Generate a system prompt from the soul file.
        
        Returns:
            A formatted system prompt incorporating all soul aspects
        """
        name = self.get_name()
        identity = self.get_section("Identity")
        personality = self.get_personality()
        comm_style = self.get_communication_style()
        proactivity = self.get_proactivity()
        values = self.get_values()
        boundaries = self.get_boundaries()
        
        prompt_parts = [
            f"You are {name}, a personal AI assistant.",
            "",
            "## Your Identity",
            identity if identity else "You are a helpful AI assistant.",
            "",
            "## Your Personality",
            personality if personality else "You are helpful, friendly, and professional.",
            "",
            "## Communication Style",
            comm_style if comm_style else "Adapt your responses to the user's needs.",
            "",
            "## Proactivity",
            proactivity if proactivity else "Respond helpfully to requests.",
            "",
            "## Core Values",
            values if values else "Be helpful, honest, and respectful.",
            "",
            "## Boundaries",
            boundaries if boundaries else "Ask before taking significant actions.",
        ]
        
        return "\n".join(prompt_parts)
    
    def update_section(self, section_name: str, new_content: str):
        """Update a specific section in the soul file.
        
        Args:
            section_name: Name of the section to update
            new_content: New content for the section
        """
        content = self.read()
        pattern = rf"(## {re.escape(section_name)}\n)(.*?)(?=\n## |\Z)"
        
        def replace_section(match):
            return f"{match.group(1)}{new_content}\n\n"
        
        new_soul = re.sub(pattern, replace_section, content, flags=re.DOTALL)
        self.soul_file.write_text(new_soul)
        self._cache = None  # Invalidate cache
        logger.info(f"Updated section '{section_name}' in soul")