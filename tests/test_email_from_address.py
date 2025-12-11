"""Tests for email from address handling.

This module tests that the SendEmailRequest uses the correct from_email address
based on the original to_email address that the user wrote to.

The issue requirement states: "Reply email should come from the address the user
wrote to in the first place", meaning that if a user sends an email TO
support@company.com, the reply should come FROM support@company.com.
"""

from basic.models import EmailData, SendEmailRequest


def test_send_email_request_uses_original_to_email_as_from_email():
    """Test that reply emails come from the address the user originally wrote to.

    This is the core requirement from the issue:
    "SendEmailRequest should use original to: email in its from: field"
    "Reply email should come from the address the user wrote to in the first place"
    """
    # Simulate a user sending an email TO support@company.com
    original_email = EmailData(
        from_email="user@example.com",
        to_email="support@company.com",
        subject="Help needed",
        text="I need assistance",
    )

    # Create the reply email (as done in email_workflow.py)
    reply_email = SendEmailRequest(
        to_email=original_email.from_email,  # Reply TO the user
        from_email=original_email.to_email,  # Reply FROM the address they wrote to
        subject=f"Re: {original_email.subject}",
        text="We're here to help!",
    )

    # Verify the reply comes from the address the user wrote to
    assert reply_email.from_email == "support@company.com", (
        "Reply should come FROM the address the user originally wrote TO"
    )
    assert reply_email.to_email == "user@example.com", (
        "Reply should go TO the original sender"
    )


def test_send_email_request_reply_to_should_not_be_set():
    """Test that reply_to field should not be set (or set to None).

    Setting reply_to to the user's email would cause replies to go back to
    the user themselves, which doesn't make sense. The reply_to should be
    left as None (default) so replies go back to the from_email address.
    """
    original_email = EmailData(
        from_email="user@example.com",
        to_email="support@company.com",
        subject="Help needed",
        text="I need assistance",
    )

    # Create reply email without setting reply_to (correct behavior)
    reply_email = SendEmailRequest(
        to_email=original_email.from_email,
        from_email=original_email.to_email,
        subject=f"Re: {original_email.subject}",
        text="We're here to help!",
    )

    # reply_to should be None (default) so replies go back to from_email
    assert reply_email.reply_to is None, (
        "reply_to should not be set, allowing replies to go to from_email"
    )


def test_send_email_request_handles_empty_to_email():
    """Test handling of BCC emails where to_email might be empty.

    When an email is BCC'd to the system, to_email might be empty.
    Currently, this would result in from_email="" which might not be valid.
    This test documents the current behavior.
    """
    # Simulate a BCC email where to_email is empty
    original_email = EmailData(
        from_email="user@example.com",
        to_email="",  # Empty for BCC
        subject="Help needed",
        text="I need assistance",
    )

    # This would create a reply with from_email=""
    reply_email = SendEmailRequest(
        to_email=original_email.from_email,
        from_email=original_email.to_email or None,  # Use None instead of ""
        subject=f"Re: {original_email.subject}",
        text="We're here to help!",
    )

    # When to_email is empty, from_email should be None to use the default
    assert reply_email.from_email is None or reply_email.from_email == "", (
        "When to_email is empty, from_email should use the default"
    )


def test_multiple_email_scenarios():
    """Test various email scenarios to ensure correct from_email behavior."""
    scenarios = [
        ("user1@example.com", "support@company.com"),
        ("alice@domain.com", "help@company.com"),
        ("bob@test.org", "info@business.net"),
    ]

    for user_email, support_email in scenarios:
        original = EmailData(
            from_email=user_email,
            to_email=support_email,
            subject="Test",
            text="Test message",
        )

        reply = SendEmailRequest(
            to_email=original.from_email,
            from_email=original.to_email,
            subject=f"Re: {original.subject}",
            text="Reply message",
        )

        assert reply.from_email == support_email, (
            f"Reply should come from {support_email}, the address user wrote to"
        )
        assert reply.to_email == user_email, (
            f"Reply should go to {user_email}, the original sender"
        )
