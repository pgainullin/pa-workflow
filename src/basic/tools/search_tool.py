"""Tool for searching the web using DuckDuckGo search."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .base import Tool

logger = logging.getLogger(__name__)


class SearchTool(Tool):
    """Tool for searching the web using DuckDuckGo search."""

    def __init__(self, max_results: int = 5):
        """Initialize the SearchTool.

        Args:
            max_results: Maximum number of search results to return (default: 5)
        """
        self.max_results = max_results

    @property
    def name(self) -> str:
        return "search"

    @property
    def description(self) -> str:
        return (
            "Search the web for information using DuckDuckGo. "
            "Input: query (search query), max_results (optional, default: 5). "
            "Output: results (list of search results with title, snippet, and URL)"
        )

    async def execute(self, **kwargs) -> dict[str, Any]:
        """Search the web for information.

        Args:
            **kwargs: Keyword arguments including:
                - query: Search query (required)
                - max_results: Maximum number of results (optional, default: 5)

        Returns:
            Dictionary with 'success' and 'results' or 'error'
        """
        query = kwargs.get("query")
        max_results = kwargs.get("max_results", self.max_results)

        if not query:
            return {"success": False, "error": "Missing required parameter: query"}

        try:
            # Use DuckDuckGo Instant Answer API
            # This is a simple, free API that doesn't require authentication
            async with httpx.AsyncClient() as client:
                # DuckDuckGo HTML search (simpler than the instant answer API)
                response = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    },
                    timeout=10.0,
                    follow_redirects=True,
                )

                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Search request failed with status {response.status_code}",
                    }

                # Parse HTML response to extract search results
                results = self._parse_duckduckgo_results(
                    response.text, max_results
                )

                if not results:
                    return {
                        "success": True,
                        "query": query,
                        "results": [],
                        "message": "No results found",
                    }

                return {
                    "success": True,
                    "query": query,
                    "results": results,
                }

        except httpx.TimeoutException:
            logger.exception("Search request timed out")
            return {"success": False, "error": "Search request timed out"}
        except Exception as e:
            logger.exception("Error performing web search")
            return {"success": False, "error": str(e)}

    def _parse_duckduckgo_results(self, html: str, max_results: int) -> list[dict]:
        """Parse DuckDuckGo HTML search results.

        Args:
            html: HTML response from DuckDuckGo
            max_results: Maximum number of results to extract

        Returns:
            List of result dictionaries with title, snippet, and url
        """
        from html.parser import HTMLParser

        class DuckDuckGoParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.results = []
                self.current_result = {}
                self.in_result = False
                self.in_title = False
                self.in_snippet = False
                self.current_data = []

            def handle_starttag(self, tag, attrs):
                attrs_dict = dict(attrs)
                
                # Result container
                if tag == "div" and attrs_dict.get("class") == "result":
                    self.in_result = True
                    self.current_result = {}
                
                # Title link
                if self.in_result and tag == "a" and "result__a" in attrs_dict.get("class", ""):
                    self.in_title = True
                    self.current_result["url"] = attrs_dict.get("href", "")
                    self.current_data = []
                
                # Snippet
                if self.in_result and tag == "a" and "result__snippet" in attrs_dict.get("class", ""):
                    self.in_snippet = True
                    self.current_data = []

            def handle_endtag(self, tag):
                if tag == "a" and self.in_title:
                    self.current_result["title"] = "".join(self.current_data).strip()
                    self.in_title = False
                    self.current_data = []
                
                if tag == "a" and self.in_snippet:
                    self.current_result["snippet"] = "".join(self.current_data).strip()
                    self.in_snippet = False
                    self.current_data = []
                
                if tag == "div" and self.in_result:
                    if "title" in self.current_result and "snippet" in self.current_result:
                        self.results.append(self.current_result.copy())
                    self.in_result = False
                    self.current_result = {}

            def handle_data(self, data):
                if self.in_title or self.in_snippet:
                    self.current_data.append(data)

        parser = DuckDuckGoParser()
        try:
            parser.feed(html)
        except Exception as e:
            logger.warning(f"Error parsing search results: {e}")
        
        return parser.results[:max_results]
