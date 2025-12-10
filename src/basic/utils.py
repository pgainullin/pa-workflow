"""Utility functions for the basic workflow package."""

import html


def text_to_html(text: str) -> str:
    """Convert plain text to simple HTML format.

    Args:
        text: Plain text string with newlines

    Returns:
        HTML-formatted string with paragraphs
    """
    # Escape HTML special characters to prevent XSS
    escaped_text = html.escape(text)
    # Split text into paragraphs (separated by double newlines)
    paragraphs = escaped_text.split("\n\n")
    # Wrap each paragraph in <p> tags, converting single newlines to <br>
    html_paragraphs = [
        f"<p>{para.replace(chr(10), '<br>')}</p>" for para in paragraphs if para.strip()
    ]
    return "".join(html_paragraphs)
