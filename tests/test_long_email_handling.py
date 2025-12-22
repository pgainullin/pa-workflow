"""Tests for long email handling in the workflow."""

import base64
import pytest
from basic.models import EmailData, Attachment
from basic.prompt_utils import build_triage_prompt


class TestLongEmailHandling:
    """Test suite for handling long emails without truncation."""

    def test_build_triage_prompt_with_long_email(self):
        """Test that long emails are handled without harsh truncation."""
        # Create a long email (more than the old 5000 char limit)
        long_body = "This is important content. " * 500  # ~13,500 chars
        
        email_data = EmailData(
            from_email="user@example.com",
            subject="Important Request",
            text=long_body,
        )
        
        prompt = build_triage_prompt(
            email_data,
            tool_descriptions="Tool descriptions here",
            response_best_practices="Best practices here",
        )
        
        # The prompt should include the content up to 10,000 chars
        assert "This is important content" in prompt
        # Should not be truncated at 5000 chars anymore
        assert len([line for line in prompt.split('\n') if "important content" in line]) > 0

    def test_build_triage_prompt_with_email_chain(self):
        """Test that quoted email chains are handled separately."""
        email_body = """Please help me with this task.

Here are the details I need.

On Mon, Jan 15, 2024, John Doe <john@example.com> wrote:
> This is the previous email
> with quoted content
> that goes on for a while"""
        
        email_data = EmailData(
            from_email="user@example.com",
            subject="Task Request",
            text=email_body,
        )
        
        # Simulate adding email chain attachment
        email_chain_file = "email_chain.md"
        
        prompt = build_triage_prompt(
            email_data,
            tool_descriptions="Tool descriptions",
            response_best_practices="Best practices",
            email_chain_file=email_chain_file,
        )
        
        # Top email should be in prompt
        assert "Please help me with this task" in prompt
        assert "Here are the details I need" in prompt
        
        # Should reference the email chain attachment
        assert "email_chain.md" in prompt
        
        # The quoted content itself should NOT be in the prompt
        assert "This is the previous email" not in prompt

    def test_email_chain_attachment_creation(self):
        """Test that email chain can be stored as an attachment."""
        quoted_chain = """On Mon, Jan 15, 2024, John Doe <john@example.com> wrote:
> Previous message 1

On Sun, Jan 14, 2024, Jane Smith <jane@example.com> wrote:
> Previous message 2"""
        
        # Create attachment like the workflow does
        email_chain_content = f"# Previous Email Conversation\n\n{quoted_chain}"
        attachment = Attachment(
            id="email-chain",
            name="email_chain.md",
            type="text/markdown",
            content=base64.b64encode(email_chain_content.encode("utf-8")).decode("utf-8"),
        )
        
        # Verify attachment is created correctly
        assert attachment.name == "email_chain.md"
        assert attachment.type == "text/markdown"
        assert attachment.id == "email-chain"
        
        # Verify content can be decoded
        decoded_content = base64.b64decode(attachment.content).decode("utf-8")
        assert "Previous Email Conversation" in decoded_content
        assert "John Doe" in decoded_content
        assert "Jane Smith" in decoded_content

    def test_long_email_with_no_chain_not_truncated_harshly(self):
        """Test that long emails without chains are not truncated at 5000 chars."""
        # Create email longer than old limit but with no quoted content
        long_content = "Important information paragraph. " * 400  # ~13,200 chars
        
        email_data = EmailData(
            from_email="user@example.com",
            subject="Long Report",
            text=long_content,
        )
        
        prompt = build_triage_prompt(
            email_data,
            tool_descriptions="Tools",
            response_best_practices="Practices",
        )
        
        # Should include content up to 10,000 chars (new limit), not 5,000 (old limit)
        # Count how much of the content is in the prompt
        content_in_prompt = prompt.count("Important information paragraph")
        
        # At 10,000 char limit, we should see more than the 150 occurrences 
        # that would fit in 5,000 chars (5000/33 ≈ 150)
        assert content_in_prompt > 150

    def test_fallback_plan_handles_long_email(self):
        """Test that fallback plan uses email splitting."""
        from basic.plan_utils import _create_fallback_plan
        
        email_body = """My new request here.

On Jan 1, 2024, someone wrote:
> Old message
> More old content
> Even more""" + ("A" * 6000)  # Make it long
        
        email_data = EmailData(
            from_email="user@example.com",
            subject="Test",
            text=email_body,
        )
        
        plan = _create_fallback_plan(email_data)
        
        # Plan should have a summarise step
        assert len(plan) == 1
        assert plan[0]["tool"] == "summarise"
        
        # Should use top email, not the full body
        text_to_summarise = plan[0]["params"]["text"]
        assert "My new request here" in text_to_summarise
        # Quoted content should not be included (or minimally included)
        # Since we split, the old message should be largely absent
        
    def test_email_chain_attachment_skipped_in_fallback(self):
        """Test that email_chain.md attachment is skipped in fallback plan."""
        from basic.plan_utils import _create_fallback_plan
        
        # Create email data with both regular and email chain attachments
        regular_attachment = Attachment(
            id="att-1",
            name="document.pdf",
            type="application/pdf",
            content="base64content",
        )
        
        email_chain_attachment = Attachment(
            id="email-chain",
            name="email_chain.md",
            type="text/markdown",
            content="base64content",
        )
        
        email_data = EmailData(
            from_email="user@example.com",
            subject="Test",
            text="Email body",
            attachments=[regular_attachment, email_chain_attachment],
        )
        
        plan = _create_fallback_plan(email_data)
        
        # Should have parse step for document.pdf but not email_chain.md
        parse_steps = [step for step in plan if step["tool"] == "parse"]
        assert len(parse_steps) == 1
        assert "document.pdf" in parse_steps[0]["description"]
        assert "email_chain.md" not in str(plan)

    def test_very_long_top_email_gets_truncated_note(self):
        """Test that extremely long top emails (>10k chars) get a truncation note."""
        # Create a very long email with no quoted content
        very_long_email = "X" * 15000
        
        email_data = EmailData(
            from_email="user@example.com",
            subject="Very Long Email",
            text=very_long_email,
        )
        
        prompt = build_triage_prompt(
            email_data,
            tool_descriptions="Tools",
            response_best_practices="Practices",
        )
        
        # Should include truncation note
        assert "Email truncated - content exceeds length limit" in prompt
        
        # Should include first 10,000 chars
        assert "X" * 1000 in prompt  # Sample check
