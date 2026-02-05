"""
Code execution tool using E2B or local subprocess.
"""

import asyncio
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import structlog

from .base import BaseTool, ToolResult

logger = structlog.get_logger()


class CodeExecutorTool(BaseTool):
    """Tool for executing code in a sandbox."""
    
    def __init__(self, e2b_api_key: str = ""):
        self.e2b_api_key = e2b_api_key
    
    @property
    def name(self) -> str:
        return "execute_code"
    
    @property
    def description(self) -> str:
        return """Execute Python code and return the output. Use this for calculations, 
        data processing, or any task that requires running code. The code runs in a 
        sandboxed environment with common libraries available (numpy, pandas, etc.)."""
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Execution timeout in seconds (default: 30, max: 120)",
                    "default": 30,
                },
            },
            "required": ["code"],
        }
    
    async def execute(self, code: str, timeout: int = 30) -> ToolResult:
        """Execute code."""
        timeout = min(timeout, 120)
        
        try:
            if self.e2b_api_key:
                return await self._e2b_execute(code, timeout)
            else:
                return await self._local_execute(code, timeout)
        except Exception as e:
            logger.error("Code execution error", error=str(e))
            return ToolResult(
                success=False,
                output="",
                error=f"Execution failed: {str(e)}",
            )
    
    async def _e2b_execute(self, code: str, timeout: int) -> ToolResult:
        """Execute using E2B sandbox."""
        try:
            from e2b_code_interpreter import Sandbox
            
            sandbox = Sandbox(api_key=self.e2b_api_key)
            try:
                execution = sandbox.run_code(code, timeout=timeout)
                
                output_parts = []
                if execution.logs.stdout:
                    output_parts.append(f"**Output:**\n{execution.logs.stdout}")
                if execution.logs.stderr:
                    output_parts.append(f"**Errors:**\n{execution.logs.stderr}")
                if execution.results:
                    for result in execution.results:
                        if hasattr(result, "text"):
                            output_parts.append(f"**Result:**\n{result.text}")
                
                output = "\n\n".join(output_parts) if output_parts else "Code executed successfully (no output)"
                
                return ToolResult(
                    success=not execution.error,
                    output=output,
                    data={"stdout": execution.logs.stdout, "stderr": execution.logs.stderr},
                    error=str(execution.error) if execution.error else None,
                )
            finally:
                sandbox.kill()
        
        except ImportError:
            logger.warning("E2B not available, falling back to local execution")
            return await self._local_execute(code, timeout)
    
    async def _local_execute(self, code: str, timeout: int) -> ToolResult:
        """Execute locally in a subprocess (more restricted)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_path = Path(f.name)
        
        try:
            process = await asyncio.create_subprocess_exec(
                "python3",
                str(temp_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Execution timed out after {timeout} seconds",
                )
            
            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")
            
            output_parts = []
            if stdout_text:
                output_parts.append(f"**Output:**\n{stdout_text}")
            if stderr_text:
                output_parts.append(f"**Errors:**\n{stderr_text}")
            
            output = "\n\n".join(output_parts) if output_parts else "Code executed successfully (no output)"
            
            return ToolResult(
                success=process.returncode == 0,
                output=output,
                data={"stdout": stdout_text, "stderr": stderr_text, "returncode": process.returncode},
                error=stderr_text if process.returncode != 0 else None,
            )
        
        finally:
            temp_path.unlink(missing_ok=True)