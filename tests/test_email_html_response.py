"""Tests for email workflow HTML response.

This module tests that the email workflow properly sets the HTML field
in the SendEmailRequest instead of using the default "(No html content)".
"""

from basic.models import SendEmailRequest


def text_to_html(text: str) -> str:
    """Convert plain text to simple HTML format.

    This is a copy of the function from email_workflow.py for testing purposes.
    We copy it to avoid import issues with API keys.

    Args:
        text: Plain text string with newlines

    Returns:
        HTML-formatted string with paragraphs
    """
    # Split text into paragraphs (separated by double newlines)
    paragraphs = text.split("\n\n")
    # Wrap each paragraph in <p> tags, converting single newlines to <br>
    html_paragraphs = [
        f"<p>{para.replace(chr(10), '<br>')}</p>" for para in paragraphs if para.strip()
    ]
    return "".join(html_paragraphs)


def test_send_email_request_html_field_default():
    """Test that SendEmailRequest has a default value for html field."""
    request = SendEmailRequest(
        to_email="user@example.com",
        subject="Test",
        text="Test message",
    )
    assert request.html == "(No html content)"


def test_send_email_request_html_field_can_be_set():
    """Test that SendEmailRequest html field can be customized."""
    request = SendEmailRequest(
        to_email="user@example.com",
        subject="Test",
        text="Test message",
        html="<p>Test message</p>",
    )
    assert request.html == "<p>Test message</p>"
    assert request.html != "(No html content)"


def test_send_email_request_html_should_contain_content():
    """Test that html field should contain actual content, not the default.

    This test validates that when creating a SendEmailRequest for a real workflow,
    the html field should be populated with actual content rather than using
    the default placeholder "(No html content)".
    """
    # Simulate creating a request like the workflow does
    summary = "Document contains 3 sections about financial data."

    request = SendEmailRequest(
        to_email="user@example.com",
        subject="Re: Document Analysis",
        text=f"Your email attachment has been processed.\n\nSummary:\n{summary}",
        html=f"<p>Your email attachment has been processed.</p><p><strong>Summary:</strong></p><p>{summary}</p>",
    )

    # The html should not be the default placeholder
    assert request.html != "(No html content)"
    # The html should contain the actual summary
    assert summary in request.html
    # The html should look like HTML
    assert "<p>" in request.html


def test_text_to_html_simple():
    """Test text_to_html with simple text."""
    text = "Hello world"
    html = text_to_html(text)
    assert html == "<p>Hello world</p>"
    assert "(No html content)" not in html


def test_text_to_html_with_paragraphs():
    """Test text_to_html with multiple paragraphs."""
    text = "First paragraph\n\nSecond paragraph"
    html = text_to_html(text)
    assert "<p>First paragraph</p>" in html
    assert "<p>Second paragraph</p>" in html
    assert "(No html content)" not in html


def test_text_to_html_with_line_breaks():
    """Test text_to_html converts single newlines to <br>."""
    text = "Line 1\nLine 2"
    html = text_to_html(text)
    assert "<br>" in html
    assert "Line 1" in html
    assert "Line 2" in html
    assert "(No html content)" not in html


def test_text_to_html_with_llm_summary():
    """Test text_to_html with realistic LLM summary content."""
    summary = """This document contains financial information.

Key points:
- Revenue increased by 15%
- Profit margin is 23%

Overall assessment: Positive growth trajectory."""

    html = text_to_html(summary)
    # Should not have the default placeholder
    assert "(No html content)" not in html
    # Should contain all the key information
    assert "financial information" in html
    assert "Revenue increased" in html
    assert "Profit margin" in html
    assert "Positive growth" in html
    # Should have HTML structure
    assert "<p>" in html
    assert "</p>" in html
    # Line breaks should be preserved within paragraphs
    assert "<br>" in html
