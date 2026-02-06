"""
Shell Command Tool - Safe execution of shell commands.

Provides a controlled interface for running shell commands
with allowlisting, output limits, and security measures.
"""

import asyncio
import logging
import os
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .base import Tool, ToolParameter, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class ShellConfig:
    """Configuration for shell command execution."""
    
    enabled: bool = True
    timeout_seconds: int = 30
    max_output_lines: int = 100
    max_output_chars: int = 10000
    
    allowed_commands: set[str] = field(default_factory=lambda: {
        "ls", "pwd", "whoami", "date", "uptime", "df", "du",
        "cat", "head", "tail", "wc", "grep", "find", "which",
        "echo", "env", "printenv", "uname", "hostname",
        "ps", "top", "free", "vmstat", "iostat",
        "ping", "curl", "wget", "dig", "nslookup", "host",
        "git", "docker", "kubectl", "npm", "yarn", "pip", "python",
        "mkdir", "touch", "cp", "mv", "rm",
        "tar", "gzip", "gunzip", "zip", "unzip",
        "jq", "sed", "awk", "sort", "uniq", "cut",
    })
    
    blocked_patterns: list[str] = field(default_factory=lambda: [
        r"rm\s+-rf\s+/",
        r"rm\s+-rf\s+~",
        r">\s*/dev/",
        r"mkfs",
        r"dd\s+if=",
        r":(){ :|:& };:",
        r"chmod\s+777",
        r"curl.*\|\s*sh",
        r"wget.*\|\s*sh",
        r"eval\s+",
        r"`.*`",
        r"\$\(.*\)",
    ])
    
    workspace_dir: Optional[str] = None


class ShellExecutor:
    """Executes shell commands with safety controls."""

    def __init__(self, config: Optional[ShellConfig] = None):
        self.config = config or ShellConfig()
        self.workspace = Path(
            self.config.workspace_dir or 
            os.getenv("WORKSPACE_DIR", str(Path.home() / ".ii-telegram-agent" / "workspace"))
        ).expanduser()
        
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _is_command_allowed(self, command: str) -> tuple[bool, str]:
        """Check if a command is allowed to execute."""
        if not self.config.enabled:
            return False, "Shell execution is disabled"
        
        for pattern in self.config.blocked_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return False, f"Command contains blocked pattern"
        
        try:
            parts = shlex.split(command)
            if not parts:
                return False, "Empty command"
            
            base_command = Path(parts[0]).name
            
            if base_command not in self.config.allowed_commands:
                if not any(cmd in base_command for cmd in self.config.allowed_commands):
                    return False, f"Command '{base_command}' is not in the allowlist"
        except ValueError as e:
            return False, f"Invalid command syntax: {e}"
        
        return True, "OK"

    async def execute(
        self,
        command: str,
        working_dir: Optional[str] = None,
    ) -> tuple[int, str, str]:
        """
        Execute a shell command.
        
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        allowed, reason = self._is_command_allowed(command)
        if not allowed:
            return -1, "", f"Command blocked: {reason}"
        
        cwd = Path(working_dir) if working_dir else self.workspace
        if not str(cwd.resolve()).startswith(str(self.workspace)):
            cwd = self.workspace
        
        try:
            env = os.environ.copy()
            env["HOME"] = str(Path.home())
            env["USER"] = os.getenv("USER", "user")
            
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd),
                env=env,
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.config.timeout_seconds,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return -1, "", f"Command timed out after {self.config.timeout_seconds} seconds"
            
            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")
            
            stdout_str = self._truncate_output(stdout_str)
            stderr_str = self._truncate_output(stderr_str)
            
            return process.returncode, stdout_str, stderr_str
            
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            return -1, "", str(e)

    def _truncate_output(self, output: str) -> str:
        """Truncate output to configured limits."""
        lines = output.split("\n")
        
        if len(lines) > self.config.max_output_lines:
            lines = lines[:self.config.max_output_lines]
            output = "\n".join(lines) + f"\n\n... (truncated, {len(lines)} lines shown)"
        
        if len(output) > self.config.max_output_chars:
            output = output[:self.config.max_output_chars] + "\n\n... (truncated)"
        
        return output

    def get_allowed_commands(self) -> list[str]:
        """Get list of allowed commands."""
        return sorted(self.config.allowed_commands)

    def add_allowed_command(self, command: str):
        """Add a command to the allowlist."""
        self.config.allowed_commands.add(command)
        logger.info(f"Added '{command}' to shell allowlist")

    def remove_allowed_command(self, command: str):
        """Remove a command from the allowlist."""
        self.config.allowed_commands.discard(command)
        logger.info(f"Removed '{command}' from shell allowlist")


_shell_executor: Optional[ShellExecutor] = None


def get_shell_executor() -> ShellExecutor:
    """Get or create ShellExecutor singleton."""
    global _shell_executor
    if _shell_executor is None:
        _shell_executor = ShellExecutor()
    return _shell_executor


async def run_command_handler(command: str, working_dir: str = "") -> ToolResult:
    """Execute a shell command."""
    try:
        executor = get_shell_executor()
        return_code, stdout, stderr = await executor.execute(command, working_dir or None)
        
        output_parts = []
        
        if stdout:
            output_parts.append(f"**Output:**\n```\n{stdout}\n```")
        
        if stderr:
            output_parts.append(f"**Errors:**\n```\n{stderr}\n```")
        
        if return_code != 0:
            output_parts.append(f"**Exit code:** {return_code}")
        
        if not output_parts:
            output_parts.append("Command completed successfully (no output)")
        
        success = return_code == 0 and "blocked" not in stderr.lower()
        
        return ToolResult(
            success=success,
            output="\n\n".join(output_parts) if success else None,
            error="\n\n".join(output_parts) if not success else None,
        )
        
    except Exception as e:
        return ToolResult(success=False, error=str(e))


async def list_allowed_commands_handler() -> ToolResult:
    """List all allowed shell commands."""
    try:
        executor = get_shell_executor()
        commands = executor.get_allowed_commands()
        
        output = "**Allowed Shell Commands:**\n\n"
        output += ", ".join(f"`{cmd}`" for cmd in commands)
        
        return ToolResult(success=True, output=output)
        
    except Exception as e:
        return ToolResult(success=False, error=str(e))


async def system_info_handler() -> ToolResult:
    """Get system information."""
    try:
        executor = get_shell_executor()
        
        info_parts = []
        
        _, hostname, _ = await executor.execute("hostname")
        info_parts.append(f"**Hostname:** {hostname.strip()}")
        
        _, uname, _ = await executor.execute("uname -a")
        info_parts.append(f"**System:** {uname.strip()}")
        
        _, uptime, _ = await executor.execute("uptime")
        info_parts.append(f"**Uptime:** {uptime.strip()}")
        
        _, df, _ = await executor.execute("df -h /")
        info_parts.append(f"**Disk Usage:**\n```\n{df}\n```")
        
        _, free, _ = await executor.execute("free -h")
        if free:
            info_parts.append(f"**Memory:**\n```\n{free}\n```")
        
        return ToolResult(success=True, output="\n\n".join(info_parts))
        
    except Exception as e:
        return ToolResult(success=False, error=str(e))


def create_shell_tools() -> list[Tool]:
    """Create shell-related tools."""
    run_command = Tool(
        name="run_command",
        description="Execute a shell command. Only whitelisted commands are allowed for safety.",
        parameters=[
            ToolParameter(
                name="command",
                param_type="string",
                description="The shell command to execute",
                required=True,
            ),
            ToolParameter(
                name="working_dir",
                param_type="string",
                description="Working directory for the command (default: workspace)",
                required=False,
            ),
        ],
        handler=run_command_handler,
    )

    list_commands = Tool(
        name="list_allowed_commands",
        description="List all shell commands that are allowed to be executed.",
        parameters=[],
        handler=list_allowed_commands_handler,
    )

    system_info = Tool(
        name="system_info",
        description="Get basic system information including hostname, OS, uptime, disk, and memory.",
        parameters=[],
        handler=system_info_handler,
    )

    return [run_command, list_commands, system_info]