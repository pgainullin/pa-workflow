"""Tests for search tool result processing in response generation."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set dummy API keys
os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key-for-testing")
os.environ.setdefault("LLAMA_CLOUD_API_KEY", "test-dummy-key-for-testing")
os.environ.setdefault("LLAMA_CLOUD_PROJECT_ID", "test-project-id")

# Mock the LLM/genai clients before importing the workflow
with patch("llama_index.llms.google_genai.GoogleGenAI"):
    with patch("google.genai.Client"):
        with patch("llama_parse.LlamaParse"):
            from basic.email_workflow import EmailWorkflow

from basic.models import EmailData


@pytest.mark.asyncio
async def test_search_results_in_user_response():
    """Test that search results are included in the user response context."""
    workflow = EmailWorkflow(timeout=60)

    email_data = EmailData(
        from_email="user@example.com",
        subject="Search for Python tutorials",
        text="Test",
    )

    results = [
        {
            "step": 1,
            "tool": "search",
            "description": "Search for Python tutorials",
            "success": True,
            "query": "Python tutorials",
            "results": [
                {
                    "title": "Python Official Documentation",
                    "url": "https://docs.python.org/3/tutorial/",
                    "snippet": "The Python Tutorial — Python documentation",
                },
                {
                    "title": "Learn Python - Free Interactive Python Tutorial",
                    "url": "https://www.learnpython.org/",
                    "snippet": "Learn Python with interactive lessons and exercises",
                },
            ],
        },
    ]

    # Mock the LLM response - capture the prompt that was passed
    captured_prompt = None
    
    def mock_complete(prompt):
        nonlocal captured_prompt
        captured_prompt = prompt
        mock_response = MagicMock()
        mock_response.__str__ = lambda x: "I found some great Python tutorials for you!"
        return mock_response
    
    workflow._llm_complete_with_retry = AsyncMock(side_effect=mock_complete)

    response = await workflow._generate_user_response(results, email_data)

    # Verify the response was generated
    assert response == "I found some great Python tutorials for you!"
    
    # Verify the prompt contained search results
    assert captured_prompt is not None
    assert "Python Official Documentation" in captured_prompt
    assert "Learn Python - Free Interactive Python Tutorial" in captured_prompt
    assert "https://docs.python.org/3/tutorial/" in captured_prompt
    assert "Found 2 search result(s)" in captured_prompt


@pytest.mark.asyncio
async def test_search_results_in_execution_log():
    """Test that search results are included in the execution log."""
    workflow = EmailWorkflow(timeout=60)

    email_data = EmailData(
        from_email="user@example.com",
        subject="Search test",
        text="Test",
    )

    results = [
        {
            "step": 1,
            "tool": "search",
            "description": "Search for AI news",
            "success": True,
            "query": "latest AI developments",
            "results": [
                {
                    "title": "OpenAI Announces GPT-5",
                    "url": "https://example.com/gpt5",
                    "snippet": "OpenAI has announced the next generation of GPT models",
                },
            ],
        },
    ]

    log = workflow._create_execution_log(results, email_data)

    # Verify search results are in the log
    assert "## Step 1: search" in log
    assert "**Search Query:** latest AI developments" in log
    assert "**Search Results:** (1 found)" in log
    assert "OpenAI Announces GPT-5" in log
    assert "https://example.com/gpt5" in log
    assert "OpenAI has announced the next generation of GPT models" in log


@pytest.mark.asyncio
async def test_search_no_results_in_execution_log():
    """Test execution log when search returns no results."""
    workflow = EmailWorkflow(timeout=60)

    email_data = EmailData(
        from_email="user@example.com",
        subject="Search test",
        text="Test",
    )

    results = [
        {
            "step": 1,
            "tool": "search",
            "description": "Search for obscure topic",
            "success": True,
            "query": "xyzabc123notfound",
            "results": [],
            "message": "No results found",
        },
    ]

    log = workflow._create_execution_log(results, email_data)

    # Verify no results message is in the log
    assert "## Step 1: search" in log
    assert "**Search Query:** xyzabc123notfound" in log
    assert "**Search Results:** No results found" in log


@pytest.mark.asyncio
async def test_search_results_in_fallback_response():
    """Test that search results are included in fallback response when LLM fails."""
    workflow = EmailWorkflow(timeout=60)

    email_data = EmailData(
        from_email="user@example.com",
        subject="Search test",
        text="Test",
    )

    results = [
        {
            "step": 1,
            "tool": "search",
            "description": "Search for Python tutorials",
            "success": True,
            "query": "Python tutorials",
            "results": [
                {
                    "title": "Python Docs",
                    "url": "https://docs.python.org/",
                    "snippet": "Official Python documentation",
                },
                {
                    "title": "Real Python",
                    "url": "https://realpython.com/",
                    "snippet": "Python tutorials and courses",
                },
            ],
        },
    ]

    # Mock LLM to fail
    workflow._llm_complete_with_retry = AsyncMock(side_effect=Exception("LLM error"))

    response = await workflow._generate_user_response(results, email_data)

    # Should use fallback response with search results
    assert "Your email has been processed successfully" in response
    assert "Search Results (2 found)" in response
    assert "1. Python Docs" in response
    assert "2. Real Python" in response
    assert "Official Python documentation" in response
    assert "execution_log.md" in response


@pytest.mark.asyncio
async def test_search_results_with_multiple_tools():
    """Test that search results work alongside other tool results."""
    workflow = EmailWorkflow(timeout=60)

    email_data = EmailData(
        from_email="user@example.com",
        subject="Complex request",
        text="Test",
    )

    results = [
        {
            "step": 1,
            "tool": "search",
            "description": "Search for information",
            "success": True,
            "query": "LlamaIndex",
            "results": [
                {
                    "title": "LlamaIndex Documentation",
                    "url": "https://docs.llamaindex.ai/",
                    "snippet": "Data framework for LLM applications",
                },
            ],
        },
        {
            "step": 2,
            "tool": "summarise",
            "description": "Summarize findings",
            "success": True,
            "summary": "LlamaIndex is a powerful data framework.",
        },
    ]

    # Mock the LLM response - capture the prompt that was passed
    captured_prompt = None
    
    def mock_complete(prompt):
        nonlocal captured_prompt
        captured_prompt = prompt
        mock_response = MagicMock()
        mock_response.__str__ = lambda x: "I found information about LlamaIndex and summarized it for you."
        return mock_response
    
    workflow._llm_complete_with_retry = AsyncMock(side_effect=mock_complete)

    response = await workflow._generate_user_response(results, email_data)

    # Verify both search and summary are in the prompt
    assert captured_prompt is not None
    assert "LlamaIndex Documentation" in captured_prompt
    assert "Data framework for LLM applications" in captured_prompt
    assert "LlamaIndex is a powerful data framework." in captured_prompt
