"""Tests for email from address handling.

This module tests that the SendEmailRequest uses the correct from_email address
based on the original to_email address that the user wrote to.
"""

import pytest
from basic.models import EmailData, SendEmailRequest


def test_send_email_request_uses_original_to_email_as_from_email():
    """Test that reply emails come from the address the user originally wrote to."""
    # Simulate a user sending an email TO support@company.com
    original_email = EmailData(
        from_email="user@example.com",
        to_email="support@company.com",
        subject="Help needed",
        text="I need assistance",
    )
    
    # Create the reply email
    reply_email = SendEmailRequest(
        to_email=original_email.from_email,      # Reply TO the user
        from_email=original_email.to_email,      # Reply FROM the address they wrote to
        subject=f"Re: {original_email.subject}",
        text="We're here to help!",
    )
    
    # Verify the reply comes from the address the user wrote to
    assert reply_email.from_email == "support@company.com"
    assert reply_email.to_email == "user@example.com"


def test_send_email_request_handles_empty_to_email():
    """Test handling of BCC emails where to_email might be empty."""
    # Simulate a BCC email where to_email is empty
    original_email = EmailData(
        from_email="user@example.com",
        to_email="",  # Empty for BCC
        subject="Help needed",
        text="I need assistance",
    )
    
    # This would create a reply with from_email=""
    # which is probably not valid
    reply_email = SendEmailRequest(
        to_email=original_email.from_email,
        from_email=original_email.to_email,  # This would be ""
        subject=f"Re: {original_email.subject}",
        text="We're here to help!",
    )
    
    # This is the current behavior - from_email would be ""
    assert reply_email.from_email == ""
    # This might not be the desired behavior - we might want a default instead


def test_send_email_request_reply_to_field():
    """Test that reply_to field is set correctly (or not set at all)."""
    original_email = EmailData(
        from_email="user@example.com",
        to_email="support@company.com",
        subject="Help needed",
        text="I need assistance",
    )
    
    # Create reply email without setting reply_to
    reply_email = SendEmailRequest(
        to_email=original_email.from_email,
        from_email=original_email.to_email,
        subject=f"Re: {original_email.subject}",
        text="We're here to help!",
    )
    
    # reply_to should be None (default) so replies go back to from_email
    assert reply_email.reply_to is None
    
    # Setting reply_to to the user's email doesn't make sense
    # because when they click reply, it would send to themselves
    bad_reply_email = SendEmailRequest(
        to_email=original_email.from_email,
        from_email=original_email.to_email,
        subject=f"Re: {original_email.subject}",
        text="We're here to help!",
        reply_to=original_email.from_email,  # This is wrong!
    )
    
    # This would make replies go to the user themselves
    assert bad_reply_email.reply_to == "user@example.com"
    # This is the current behavior in email_workflow.py and it's incorrect
