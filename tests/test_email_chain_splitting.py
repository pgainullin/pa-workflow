"""Tests for email chain splitting functionality."""

from basic.utils import split_email_chain


class TestEmailChainSplitting:
    """Test suite for split_email_chain function."""

    def test_simple_quote_marker(self):
        """Test splitting email with simple > quote markers."""
        email_body = """Hi there,

This is my reply.

> Previous message
> quoted here
> with multiple lines"""
        
        top, chain = split_email_chain(email_body)
        
        assert "This is my reply" in top
        assert "Previous message" in chain
        assert "quoted here" in chain
        assert len(chain) > 0

    def test_on_date_wrote_pattern(self):
        """Test splitting email with 'On [date] wrote:' pattern."""
        email_body = """Thanks for the update!

I'll review this today.

On Mon, Jan 15, 2024 at 10:30 AM, John Doe <john@example.com> wrote:
> Here is the previous message
> that was sent earlier"""
        
        top, chain = split_email_chain(email_body)
        
        assert "Thanks for the update" in top
        assert "I'll review this today" in top
        assert "On Mon, Jan 15, 2024" in chain
        assert "previous message" in chain

    def test_from_header_pattern(self):
        """Test splitting email with From: header."""
        email_body = """This is my response.

From: sender@example.com
Sent: Monday, January 15, 2024
To: recipient@example.com
Subject: Original Subject

Original message content here."""
        
        top, chain = split_email_chain(email_body)
        
        assert "This is my response" in top
        assert "From: sender@example.com" in chain
        assert "Original message content" in chain

    def test_original_message_separator(self):
        """Test splitting with ----- Original Message ----- separator."""
        email_body = """Here is my new message.

----- Original Message -----
From: someone@example.com
Date: Jan 15, 2024
Previous email content"""
        
        top, chain = split_email_chain(email_body)
        
        assert "Here is my new message" in top
        assert "Original Message" in chain
        assert "Previous email content" in chain

    def test_outlook_separator(self):
        """Test splitting with Outlook's underscore separator."""
        email_body = """My reply to the email.

________________________________
From: Alice <alice@example.com>
Sent: Monday, January 15, 2024 9:00 AM
To: Bob <bob@example.com>
Subject: RE: Project Update

Previous email text"""
        
        top, chain = split_email_chain(email_body)
        
        assert "My reply to the email" in top
        assert "From: Alice" in chain
        assert "Previous email text" in chain

    def test_no_quoted_content(self):
        """Test email with no quoted content returns empty chain."""
        email_body = """This is a simple email
with no quoted content
just multiple lines."""
        
        top, chain = split_email_chain(email_body)
        
        assert top == email_body.strip()
        assert chain == ""

    def test_empty_email(self):
        """Test empty email returns empty strings."""
        top, chain = split_email_chain("")
        assert top == ""
        assert chain == ""
        
        top, chain = split_email_chain("   ")
        assert top == ""
        assert chain == ""

    def test_multiple_separators(self):
        """Test email with multiple separator patterns uses earliest."""
        email_body = """My response here.

> Some quote
> More quote

On Jan 1, someone wrote:
Even more old content"""
        
        top, chain = split_email_chain(email_body)
        
        # Should split at the first quote marker
        assert "My response here" in top
        assert "Some quote" in chain
        assert "On Jan 1" in chain

    def test_consecutive_quote_markers(self):
        """Test that consecutive quote markers are recognized."""
        email_body = """New message

> First quoted line
> Second quoted line
> Third quoted line

More text"""
        
        top, chain = split_email_chain(email_body)
        
        assert "New message" in top
        assert "First quoted line" in chain
        assert "More text" in chain

    def test_html_stripped_content(self):
        """Test splitting works with HTML-stripped content."""
        # This simulates what would happen after HTML is stripped
        email_body = """Please review the attached document.

Best regards,
John

On Tue, Jan 16, 2024 at 2:15 PM Jane Smith jane@example.com wrote:
Thanks for sending this over. I will take a look.

Jane"""
        
        top, chain = split_email_chain(email_body)
        
        assert "Please review" in top
        assert "Best regards" in top
        assert "On Tue, Jan 16" in chain
        assert "Jane Smith" in chain

    def test_very_long_email_no_chain(self):
        """Test that a very long email with no chain markers returns all as top email."""
        long_email = "This is a very long email. " * 1000
        
        top, chain = split_email_chain(long_email)
        
        assert len(top) == len(long_email.strip())
        assert chain == ""

    def test_whitespace_handling(self):
        """Test that whitespace is properly handled."""
        email_body = """   My message

    > Quoted content
    > More quoted content
    """

        top, chain = split_email_chain(email_body)

        # Leading/trailing whitespace should be stripped
        assert top.strip() == "My message"
        assert "Quoted content" in chain
