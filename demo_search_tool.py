"""Demo script to demonstrate the Search tool functionality.

This script shows how the Search tool can be used to perform semantic search
through text content using RAG (Retrieval-Augmented Generation).
"""

import asyncio
import os
from unittest.mock import MagicMock, AsyncMock, patch

# Set dummy API keys for demo
os.environ.setdefault("GEMINI_API_KEY", "demo-key")
os.environ.setdefault("LLAMA_CLOUD_API_KEY", "demo-key")
os.environ.setdefault("LLAMA_CLOUD_PROJECT_ID", "demo-project")
os.environ.setdefault("OPENAI_API_KEY", "demo-openai-key")


async def main():
    """Demonstrate the Search tool with a mock setup."""
    print("=" * 80)
    print("Search Tool Demo")
    print("=" * 80)
    print()

    # Import the SearchTool
    from src.basic.tools import SearchTool

    # Sample text about LlamaIndex
    sample_text = """
    LlamaIndex is a framework for building data-backed LLM applications.
    It specializes in agentic workflows and Retrieval-Augmented Generation (RAG).
    
    The framework enables developers to build AI applications that combine Large 
    Language Models with real-world data sources. LlamaIndex addresses the challenge 
    that LLMs are trained on public data with knowledge cutoffs, but most valuable 
    business applications require access to private documents, databases, APIs, 
    and real-time information.
    
    Key features include:
    - Document loading and parsing
    - Vector indexing for efficient retrieval
    - Query engines for asking questions over data
    - Chat engines for conversational interfaces
    - Multi-modal support for images, videos, and documents
    
    LlamaIndex supports dozens of LLM providers including OpenAI, Anthropic, and 
    local models, with hundreds of data connectors for ingesting diverse data sources.
    """

    # Create a SearchTool instance with mock embedding
    mock_embed_model = MagicMock()
    tool = SearchTool(embed_model=mock_embed_model)

    print("Sample Text:")
    print("-" * 80)
    print(sample_text.strip())
    print()
    print("=" * 80)
    print()

    # Mock the VectorStoreIndex to simulate search results
    with patch("src.basic.tools.VectorStoreIndex") as mock_index_class:
        mock_index = MagicMock()
        mock_query_engine = MagicMock()

        # Simulate query responses for different queries
        queries = [
            "What is LlamaIndex?",
            "What features does LlamaIndex provide?",
            "Which LLM providers are supported?",
        ]

        for query in queries:
            print(f"Query: {query}")
            print("-" * 80)

            # Mock response for this query
            mock_response = MagicMock()
            mock_response.__str__ = lambda x: f"LlamaIndex is a framework that {query.lower()}"

            # Create mock nodes with relevant content
            mock_node = MagicMock()
            if "what is" in query.lower():
                content = "LlamaIndex is a framework for building data-backed LLM applications."
                score = 0.95
            elif "features" in query.lower():
                content = "Key features include document loading, vector indexing, and query engines."
                score = 0.88
            else:
                content = "LlamaIndex supports dozens of LLM providers including OpenAI and Anthropic."
                score = 0.91

            mock_node.node.get_content = MagicMock(return_value=content)
            mock_node.score = score

            mock_response.source_nodes = [mock_node]
            mock_query_engine.aquery = AsyncMock(return_value=mock_response)

            mock_index.as_query_engine = MagicMock(return_value=mock_query_engine)
            mock_index_class.from_documents = MagicMock(return_value=mock_index)

            # Execute the search
            result = await tool.execute(text=sample_text, query=query, top_k=1)

            # Display results
            if result["success"]:
                print(f"✓ Search completed successfully")
                print(f"  Top Result (score: {result['results'][0]['score']:.2f}):")
                print(f"  {result['results'][0]['text']}")
                print()
            else:
                print(f"✗ Search failed: {result.get('error', 'Unknown error')}")
                print()

    print("=" * 80)
    print("Demo Complete!")
    print()
    print("The Search tool enables semantic search through text content using")
    print("LlamaIndex's RAG capabilities. It can be used to find relevant")
    print("information within documents, emails, or any text-based content.")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
