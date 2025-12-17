"""Demo script to demonstrate the Search tool functionality.

This script shows how the Search tool can be used to perform web search
using DuckDuckGo.
"""

import asyncio
import os
from unittest.mock import MagicMock, AsyncMock, patch

# Set dummy API keys for demo
os.environ.setdefault("GEMINI_API_KEY", "demo-key")
os.environ.setdefault("LLAMA_CLOUD_API_KEY", "demo-key")
os.environ.setdefault("LLAMA_CLOUD_PROJECT_ID", "demo-project")


async def main():
    """Demonstrate the Search tool with a mock setup."""
    print("=" * 80)
    print("Web Search Tool Demo")
    print("=" * 80)
    print()

    # Import the SearchTool
    from src.basic.tools import SearchTool

    # Create a SearchTool instance
    tool = SearchTool(max_results=3)

    print("Search Tool Configuration:")
    print("-" * 80)
    print(f"Tool Name: {tool.name}")
    print(f"Description: {tool.description}")
    print(f"Max Results: {tool.max_results}")
    print()
    print("=" * 80)
    print()

    # Mock httpx client to simulate web search
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        
        # Simulate query responses for different queries
        queries = [
            "What is LlamaIndex?",
            "Latest AI news",
            "Python programming tutorials",
        ]

        for query in queries:
            print(f"Query: {query}")
            print("-" * 80)

            # Mock HTML response with search results
            mock_response = MagicMock()
            mock_response.status_code = 200
            
            if "llamaindex" in query.lower():
                mock_response.text = """
                <html>
                    <div class="result">
                        <a class="result__a" href="https://docs.llamaindex.ai/">LlamaIndex Documentation</a>
                        <a class="result__snippet">Official documentation for LlamaIndex, a framework for building data-backed LLM applications.</a>
                    </div>
                    <div class="result">
                        <a class="result__a" href="https://github.com/run-llama/llama_index">LlamaIndex GitHub</a>
                        <a class="result__snippet">LlamaIndex is a data framework for LLM applications to ingest, structure, and access data.</a>
                    </div>
                </html>
                """
            elif "ai news" in query.lower():
                mock_response.text = """
                <html>
                    <div class="result">
                        <a class="result__a" href="https://example.com/ai-news">Latest AI Developments</a>
                        <a class="result__snippet">Breaking news in artificial intelligence and machine learning technologies.</a>
                    </div>
                </html>
                """
            else:
                mock_response.text = """
                <html>
                    <div class="result">
                        <a class="result__a" href="https://python.org/tutorials">Python Tutorials</a>
                        <a class="result__snippet">Learn Python programming with official tutorials and guides.</a>
                    </div>
                </html>
                """
            
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Execute the search
            result = await tool.execute(query=query, max_results=3)

            # Display results
            if result["success"]:
                print(f"✓ Search completed successfully")
                print(f"  Found {len(result['results'])} result(s):")
                for i, res in enumerate(result['results'], 1):
                    print(f"  {i}. {res['title']}")
                    print(f"     URL: {res['url']}")
                    print(f"     Snippet: {res['snippet']}")
                print()
            else:
                print(f"✗ Search failed: {result.get('error', 'Unknown error')}")
                print()

    print("=" * 80)
    print("Demo Complete!")
    print()
    print("The Search tool enables web search using DuckDuckGo.")
    print("It can be used to find information on the internet, retrieve")
    print("current news, research topics, or answer questions using web results.")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
