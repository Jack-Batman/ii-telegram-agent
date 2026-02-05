"""
User Profile Manager - User information and preferences.

This module handles reading and parsing the USER.md file which contains
information about the user to help personalize the assistant's responses.
"""

import os
import re
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class UserProfileManager:
    """Manages user profile information from USER.md."""
    
    DEFAULT_PROFILE = """# User Profile

## Identity
- **Name**: Not specified
- **Timezone**: UTC

## About
Not specified

## Goals & Priorities
Not specified

## Communication Preferences
Not specified

## Notes
<!-- Add any other information you want your assistant to know -->
"""
    
    def __init__(self, workspace_dir: Optional[str] = None):
        """Initialize the user profile manager.
        
        Args:
            workspace_dir: Path to the workspace directory containing USER.md
        """
        self.workspace_dir = Path(workspace_dir or os.getenv("WORKSPACE_DIR", "~/.ii-telegram-agent/workspace"))
        self.workspace_dir = self.workspace_dir.expanduser()
        self.profile_file = self.workspace_dir / "USER.md"
        self._ensure_profile_file()
        self._cache = None
    
    def _ensure_profile_file(self):
        """Ensure the profile file exists with default content."""
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        
        if not self.profile_file.exists():
            self.profile_file.write_text(self.DEFAULT_PROFILE)
            logger.info(f"Created user profile at {self.profile_file}")
    
    def read(self) -> str:
        """Read the entire profile file.
        
        Returns:
            The contents of USER.md
        """
        try:
            return self.profile_file.read_text()
        except Exception as e:
            logger.error(f"Error reading profile file: {e}")
            return self.DEFAULT_PROFILE
    
    def get_section(self, section_name: str) -> str:
        """Get the content of a specific section.
        
        Args:
            section_name: Name of the section
            
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
        """Get the user's name.
        
        Returns:
            The user's name, or "User" if not specified
        """
        identity = self.get_section("Identity")
        
        # Try to extract name from "**Name**: value"
        match = re.search(r"\*\*Name\*\*:\s*(.+)", identity)
        if match:
            name = match.group(1).strip()
            if name and name.lower() != "not specified":
                return name
        
        return "User"
    
    def get_timezone(self) -> str:
        """Get the user's timezone.
        
        Returns:
            The user's timezone, or "UTC" if not specified
        """
        identity = self.get_section("Identity")
        
        match = re.search(r"\*\*Timezone\*\*:\s*(.+)", identity)
        if match:
            tz = match.group(1).strip()
            if tz and tz.lower() != "not specified":
                return tz
        
        return "UTC"
    
    def get_about(self) -> str:
        """Get information about the user.
        
        Returns:
            About section content
        """
        about = self.get_section("About")
        if about.lower() == "not specified":
            return ""
        return about
    
    def get_goals(self) -> str:
        """Get user's goals and priorities.
        
        Returns:
            Goals section content
        """
        goals = self.get_section("Goals & Priorities")
        if goals.lower() == "not specified":
            return ""
        return goals
    
    def get_communication_preferences(self) -> str:
        """Get user's communication preferences.
        
        Returns:
            Communication preferences content
        """
        prefs = self.get_section("Communication Preferences")
        if prefs.lower() == "not specified":
            return ""
        return prefs
    
    def get_context_for_prompt(self) -> str:
        """Generate user context for inclusion in prompts.
        
        Returns:
            Formatted user context string
        """
        parts = []
        
        name = self.get_name()
        if name != "User":
            parts.append(f"**User's Name:** {name}")
        
        tz = self.get_timezone()
        if tz != "UTC":
            parts.append(f"**Timezone:** {tz}")
        
        about = self.get_about()
        if about:
            parts.append(f"**About the User:**\n{about}")
        
        goals = self.get_goals()
        if goals:
            parts.append(f"**User's Goals:**\n{goals}")
        
        prefs = self.get_communication_preferences()
        if prefs:
            parts.append(f"**Communication Preferences:**\n{prefs}")
        
        if parts:
            return "\n\n".join(parts)
        
        return "No user profile information available."
    
    def update_section(self, section_name: str, new_content: str):
        """Update a specific section in the profile file.
        
        Args:
            section_name: Name of the section to update
            new_content: New content for the section
        """
        content = self.read()
        pattern = rf"(## {re.escape(section_name)}\n)(.*?)(?=\n## |\Z)"
        
        def replace_section(match):
            return f"{match.group(1)}{new_content}\n\n"
        
        new_profile = re.sub(pattern, replace_section, content, flags=re.DOTALL)
        self.profile_file.write_text(new_profile)
        self._cache = None
        logger.info(f"Updated section '{section_name}' in user profile")
    
    def update_name(self, name: str):
        """Update the user's name.
        
        Args:
            name: The new name
        """
        identity = self.get_section("Identity")
        new_identity = re.sub(
            r"(\*\*Name\*\*:\s*).+",
            f"\\1{name}",
            identity
        )
        self.update_section("Identity", new_identity)
    
    def update_timezone(self, timezone: str):
        """Update the user's timezone.
        
        Args:
            timezone: The new timezone
        """
        identity = self.get_section("Identity")
        new_identity = re.sub(
            r"(\*\*Timezone\*\*:\s*).+",
            f"\\1{timezone}",
            identity
        )
        self.update_section("Identity", new_identity)