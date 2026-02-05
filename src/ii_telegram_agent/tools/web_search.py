"""
Web search tool using DuckDuckGo or Tavily.
"""

from typing import Any

import httpx
import structlog

from .base import BaseTool, ToolResult

logger = structlog.get_logger()


class WebSearchTool(BaseTool):
    """Tool for searching the web."""
    
    def __init__(self, tavily_api_key: str = ""):
        self.tavily_api_key = tavily_api_key
    
    @property
    def name(self) -> str:
        return "web_search"
    
    @property
    def description(self) -> str:
        return """Search the web for information. Use this when you need to find current information, 
        facts, news, or any information that might not be in your training data. 
        Returns relevant search results with titles, URLs, and snippets."""
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find information about",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        }
    
    async def execute(self, query: str, max_results: int = 5) -> ToolResult:
        """Execute web search."""
        try:
            if self.tavily_api_key:
                return await self._tavily_search(query, max_results)
            else:
                return await self._duckduckgo_search(query, max_results)
        except Exception as e:
            logger.error("Web search error", error=str(e))
            return ToolResult(
                success=False,
                output="",
                error=f"Search failed: {str(e)}",
            )
    
    async def _tavily_search(self, query: str, max_results: int) -> ToolResult:
        """Search using Tavily API."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.tavily_api_key,
                    "query": query,
                    "max_results": max_results,
                    "include_answer": True,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
        
        results = []
        if data.get("answer"):
            results.append(f"**Summary:** {data['answer']}\n")
        
        for result in data.get("results", [])[:max_results]:
            results.append(
                f"**{result['title']}**\n"
                f"URL: {result['url']}\n"
                f"{result.get('content', '')[:500]}\n"
            )
        
        output = "\n---\n".join(results) if results else "No results found."
        
        return ToolResult(
            success=True,
            output=output,
            data=data,
        )
    
    async def _duckduckgo_search(self, query: str, max_results: int) -> ToolResult:
        """Search using DuckDuckGo."""
        try:
            from duckduckgo_search import DDGS
            
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append(
                        f"**{r['title']}**\n"
                        f"URL: {r['href']}\n"
                        f"{r['body'][:500]}\n"
                    )
            
            output = "\n---\n".join(results) if results else "No results found."
            
            return ToolResult(
                success=True,
                output=output,
                data=results,
            )
        except Exception as e:
            logger.error("DuckDuckGo search error", error=str(e))
            return ToolResult(
                success=False,
                output="",
                error=f"DuckDuckGo search failed: {str(e)}",
            )