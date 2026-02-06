"""
File Operations Tool - Read, write, and search files on the system.

Provides safe file operations within a configurable workspace.
"""

import fnmatch
import logging
import os
import re
from pathlib import Path
from typing import Optional

from .base import Tool, ToolParameter, ToolResult

logger = logging.getLogger(__name__)


class FileManager:
    """Manages file operations within a safe workspace."""

    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace_dir = Path(
            workspace_dir or os.getenv("WORKSPACE_DIR", str(Path.home() / ".ii-telegram-agent" / "workspace"))
        ).expanduser().resolve()
        
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        
        self.allowed_extensions = {
            ".txt", ".md", ".json", ".yaml", ".yml", ".toml",
            ".py", ".js", ".ts", ".html", ".css", ".sh",
            ".log", ".csv", ".xml", ".ini", ".conf", ".env",
        }
        
        self.blocked_paths = {
            "/etc/passwd", "/etc/shadow", ".ssh", ".gnupg",
            ".aws", ".gcloud", "credentials",
        }

    def _is_safe_path(self, path: Path) -> bool:
        """Check if a path is safe to access."""
        try:
            resolved = path.resolve()
            
            if not str(resolved).startswith(str(self.workspace_dir)):
                logger.warning(f"Path outside workspace: {path}")
                return False
            
            path_str = str(resolved).lower()
            for blocked in self.blocked_paths:
                if blocked.lower() in path_str:
                    logger.warning(f"Blocked path pattern: {path}")
                    return False
            
            return True
        except Exception:
            return False

    def _normalize_path(self, path: str) -> Path:
        """Normalize a path relative to workspace."""
        p = Path(path)
        
        if not p.is_absolute():
            p = self.workspace_dir / p
        
        return p

    def read_file(self, path: str, max_lines: Optional[int] = None) -> str:
        """Read a file's contents."""
        file_path = self._normalize_path(path)
        
        if not self._is_safe_path(file_path):
            raise PermissionError(f"Access denied: {path}")
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        if not file_path.is_file():
            raise IsADirectoryError(f"Path is a directory: {path}")
        
        content = file_path.read_text()
        
        if max_lines:
            lines = content.split("\n")
            if len(lines) > max_lines:
                content = "\n".join(lines[:max_lines])
                content += f"\n\n... (truncated, {len(lines) - max_lines} more lines)"
        
        return content

    def write_file(self, path: str, content: str, append: bool = False) -> str:
        """Write content to a file."""
        file_path = self._normalize_path(path)
        
        if not self._is_safe_path(file_path):
            raise PermissionError(f"Access denied: {path}")
        
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        mode = "a" if append else "w"
        with open(file_path, mode) as f:
            f.write(content)
        
        action = "Appended to" if append else "Wrote"
        return f"{action} {len(content)} characters to {file_path.name}"

    def list_files(
        self,
        path: str = ".",
        pattern: str = "*",
        recursive: bool = False,
    ) -> list[str]:
        """List files in a directory."""
        dir_path = self._normalize_path(path)
        
        if not self._is_safe_path(dir_path):
            raise PermissionError(f"Access denied: {path}")
        
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {path}")
        
        if not dir_path.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {path}")
        
        files = []
        if recursive:
            for file_path in dir_path.rglob(pattern):
                if file_path.is_file():
                    files.append(str(file_path.relative_to(dir_path)))
        else:
            for file_path in dir_path.glob(pattern):
                if file_path.is_file():
                    files.append(file_path.name)
        
        return sorted(files)

    def search_files(
        self,
        pattern: str,
        path: str = ".",
        content_search: bool = False,
    ) -> list[dict]:
        """Search for files by name or content."""
        dir_path = self._normalize_path(path)
        
        if not self._is_safe_path(dir_path):
            raise PermissionError(f"Access denied: {path}")
        
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {path}")
        
        results = []
        
        for file_path in dir_path.rglob("*"):
            if not file_path.is_file():
                continue
            
            if not self._is_safe_path(file_path):
                continue
            
            if content_search:
                try:
                    content = file_path.read_text()
                    matches = list(re.finditer(pattern, content, re.IGNORECASE))
                    if matches:
                        results.append({
                            "file": str(file_path.relative_to(dir_path)),
                            "matches": len(matches),
                            "preview": content[max(0, matches[0].start() - 20):matches[0].end() + 50],
                        })
                except (UnicodeDecodeError, PermissionError):
                    pass
            else:
                if fnmatch.fnmatch(file_path.name.lower(), pattern.lower()):
                    results.append({
                        "file": str(file_path.relative_to(dir_path)),
                        "size": file_path.stat().st_size,
                    })
        
        return results

    def delete_file(self, path: str) -> str:
        """Delete a file."""
        file_path = self._normalize_path(path)
        
        if not self._is_safe_path(file_path):
            raise PermissionError(f"Access denied: {path}")
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        if file_path.is_dir():
            raise IsADirectoryError(f"Cannot delete directory: {path}")
        
        file_path.unlink()
        return f"Deleted: {file_path.name}"

    def create_directory(self, path: str) -> str:
        """Create a directory."""
        dir_path = self._normalize_path(path)
        
        if not self._is_safe_path(dir_path):
            raise PermissionError(f"Access denied: {path}")
        
        dir_path.mkdir(parents=True, exist_ok=True)
        return f"Created directory: {path}"


_file_manager: Optional[FileManager] = None


def get_file_manager() -> FileManager:
    """Get or create FileManager singleton."""
    global _file_manager
    if _file_manager is None:
        _file_manager = FileManager()
    return _file_manager


async def read_file_handler(path: str, max_lines: int = 100) -> ToolResult:
    """Read a file."""
    try:
        manager = get_file_manager()
        content = manager.read_file(path, max_lines)
        return ToolResult(success=True, output=f"**File: {path}**\n```\n{content}\n```")
    except Exception as e:
        return ToolResult(success=False, error=str(e))


async def write_file_handler(path: str, content: str, append: bool = False) -> ToolResult:
    """Write to a file."""
    try:
        manager = get_file_manager()
        result = manager.write_file(path, content, append)
        return ToolResult(success=True, output=result)
    except Exception as e:
        return ToolResult(success=False, error=str(e))


async def list_files_handler(path: str = ".", pattern: str = "*", recursive: bool = False) -> ToolResult:
    """List files in a directory."""
    try:
        manager = get_file_manager()
        files = manager.list_files(path, pattern, recursive)
        
        if not files:
            return ToolResult(success=True, output="No files found.")
        
        output = f"**Files in {path}:**\n" + "\n".join(f"- {f}" for f in files[:50])
        if len(files) > 50:
            output += f"\n\n... and {len(files) - 50} more files"
        
        return ToolResult(success=True, output=output)
    except Exception as e:
        return ToolResult(success=False, error=str(e))


async def search_files_handler(pattern: str, path: str = ".", search_content: bool = False) -> ToolResult:
    """Search for files."""
    try:
        manager = get_file_manager()
        results = manager.search_files(pattern, path, search_content)
        
        if not results:
            return ToolResult(success=True, output="No matches found.")
        
        output_lines = [f"**Search Results ({len(results)} matches):**"]
        for r in results[:20]:
            if "preview" in r:
                output_lines.append(f"- **{r['file']}** ({r['matches']} matches)\n  `{r['preview'][:60]}...`")
            else:
                output_lines.append(f"- {r['file']} ({r['size']} bytes)")
        
        if len(results) > 20:
            output_lines.append(f"\n... and {len(results) - 20} more matches")
        
        return ToolResult(success=True, output="\n".join(output_lines))
    except Exception as e:
        return ToolResult(success=False, error=str(e))


def create_file_tools() -> list[Tool]:
    """Create file operation tools."""
    read_file = Tool(
        name="read_file",
        description="Read the contents of a file in the workspace.",
        parameters=[
            ToolParameter(
                name="path",
                param_type="string",
                description="Path to the file (relative to workspace or absolute)",
                required=True,
            ),
            ToolParameter(
                name="max_lines",
                param_type="integer",
                description="Maximum lines to read (default: 100)",
                required=False,
            ),
        ],
        handler=read_file_handler,
    )

    write_file = Tool(
        name="write_file",
        description="Write content to a file in the workspace.",
        parameters=[
            ToolParameter(
                name="path",
                param_type="string",
                description="Path to the file",
                required=True,
            ),
            ToolParameter(
                name="content",
                param_type="string",
                description="Content to write",
                required=True,
            ),
            ToolParameter(
                name="append",
                param_type="boolean",
                description="Append to file instead of overwriting (default: false)",
                required=False,
            ),
        ],
        handler=write_file_handler,
    )

    list_files = Tool(
        name="list_files",
        description="List files in a directory.",
        parameters=[
            ToolParameter(
                name="path",
                param_type="string",
                description="Directory path (default: current workspace)",
                required=False,
            ),
            ToolParameter(
                name="pattern",
                param_type="string",
                description="Glob pattern to filter files (default: *)",
                required=False,
            ),
            ToolParameter(
                name="recursive",
                param_type="boolean",
                description="Search recursively (default: false)",
                required=False,
            ),
        ],
        handler=list_files_handler,
    )

    search_files = Tool(
        name="search_files",
        description="Search for files by name pattern or content.",
        parameters=[
            ToolParameter(
                name="pattern",
                param_type="string",
                description="Search pattern (glob for names, regex for content)",
                required=True,
            ),
            ToolParameter(
                name="path",
                param_type="string",
                description="Directory to search in (default: workspace)",
                required=False,
            ),
            ToolParameter(
                name="search_content",
                param_type="boolean",
                description="Search file contents instead of names (default: false)",
                required=False,
            ),
        ],
        handler=search_files_handler,
    )

    return [read_file, write_file, list_files, search_files]