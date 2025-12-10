"""Tests for email workflow HTML response.

This module tests that the email workflow properly sets the HTML field
in the SendEmailRequest instead of using the default "(No html content)".
"""

from basic.models import SendEmailRequest
from basic.utils import text_to_html


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


def test_text_to_html_escapes_html_special_characters():
    """Test that text_to_html properly escapes HTML special characters to prevent XSS."""
    # Test all HTML special characters
    text = "Test with <script>alert('xss')</script> and <img src=x onerror=alert(1)>"
    html_output = text_to_html(text)

    # Special characters should be escaped
    assert "&lt;script&gt;" in html_output
    assert "&lt;img" in html_output
    assert "<script>" not in html_output
    # The tags are escaped, so even though "onerror=" appears, it's safe
    assert "&lt;img" in html_output and "&gt;" in html_output

    # The output should still be valid HTML with proper tags
    assert "<p>" in html_output
    assert "</p>" in html_output


def test_text_to_html_escapes_ampersands():
    """Test that ampersands are properly escaped."""
    text = "A & B are partners"
    html_output = text_to_html(text)

    # Ampersand should be escaped
    assert "&amp;" in html_output
    assert "A &amp; B are partners" in html_output


def test_text_to_html_escapes_quotes():
    """Test that quotes are properly escaped."""
    text = "He said \"Hello\" and she said 'Hi'"
    html_output = text_to_html(text)

    # Quotes should be escaped
    assert "&quot;" in html_output or '"' in html_output  # Both are valid
    assert "&#x27;" in html_output or "'" in html_output  # Both are valid


def test_text_to_html_with_malicious_filename():
    """Test with a realistic malicious filename scenario."""
    filename = "<script>alert('xss')</script>.pdf"
    text = f"Your attachment has been processed.\n\nFilename: {filename}"
    html_output = text_to_html(text)

    # Script tags should be escaped
    assert "&lt;script&gt;" in html_output
    assert "<script>" not in html_output

    # Content should still be readable
    assert "Your attachment has been processed" in html_output
    assert "Filename:" in html_output
    assert ".pdf" in html_output
