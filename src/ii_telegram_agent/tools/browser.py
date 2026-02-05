"""
Browser tool for web page interaction.
"""

from typing import Any

import httpx
import structlog
from bs4 import BeautifulSoup

from .base import BaseTool, ToolResult

logger = structlog.get_logger()


class BrowserTool(BaseTool):
    """Tool for browsing web pages."""
    
    def __init__(self, browserless_api_key: str = ""):
        self.browserless_api_key = browserless_api_key
    
    @property
    def name(self) -> str:
        return "browse_webpage"
    
    @property
    def description(self) -> str:
        return """Visit a webpage and extract its content. Use this to read articles, 
        documentation, or any web page content. Returns the main text content of the page."""
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL of the webpage to visit",
                },
                "extract_links": {
                    "type": "boolean",
                    "description": "Whether to extract links from the page (default: false)",
                    "default": False,
                },
            },
            "required": ["url"],
        }
    
    async def execute(self, url: str, extract_links: bool = False) -> ToolResult:
        """Execute web page browsing."""
        try:
            async with httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                element.decompose()
            
            title = soup.title.string if soup.title else "No title"
            
            main_content = soup.find("main") or soup.find("article") or soup.find("body")
            if main_content:
                text = main_content.get_text(separator="\n", strip=True)
            else:
                text = soup.get_text(separator="\n", strip=True)
            
            text = "\n".join(line.strip() for line in text.split("\n") if line.strip())
            text = text[:10000]
            
            output = f"**Title:** {title}\n**URL:** {url}\n\n**Content:**\n{text}"
            
            data: dict[str, Any] = {"title": title, "url": url, "content": text}
            
            if extract_links:
                links = []
                for a in soup.find_all("a", href=True)[:20]:
                    href = a["href"]
                    if href.startswith("http"):
                        links.append({"text": a.get_text(strip=True)[:100], "url": href})
                data["links"] = links
                if links:
                    output += "\n\n**Links:**\n"
                    for link in links:
                        output += f"- [{link['text']}]({link['url']})\n"
            
            return ToolResult(
                success=True,
                output=output,
                data=data,
            )
        
        except Exception as e:
            logger.error("Browser error", url=url, error=str(e))
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to browse {url}: {str(e)}",
            )