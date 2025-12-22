"""Tests for plan_utils module, specifically the _create_fallback_plan helper function."""

from basic.models import Attachment, EmailData
from basic.plan_utils import _create_fallback_plan, parse_plan


class TestCreateFallbackPlan:
    """Tests for the _create_fallback_plan helper function."""

    def test_fallback_plan_without_attachments(self):
        """Test that fallback plan is created correctly for emails without attachments."""
        email_data = EmailData(
            from_email="test@example.com",
            subject="Test Subject",
            text="This is test email content.",
        )

        plan = _create_fallback_plan(email_data)

        # Should have only one step: summarise
        assert len(plan) == 1
        assert plan[0]["tool"] == "summarise"
        assert plan[0]["params"]["text"] == "This is test email content."
        assert plan[0]["description"] == "Summarize email content"

    def test_fallback_plan_with_single_attachment(self):
        """Test that fallback plan includes parse steps for attachments."""
        attachment = Attachment(
            id="att-1",
            name="document.pdf",
            type="application/pdf",
            file_id="file-123",
        )
        email_data = EmailData(
            from_email="test@example.com",
            subject="Test Subject",
            text="Email with attachment",
            attachments=[attachment],
        )

        plan = _create_fallback_plan(email_data)

        # Should have 2 steps: parse attachment + summarise
        assert len(plan) == 2
        assert plan[0]["tool"] == "parse"
        assert plan[0]["params"]["file_id"] == "att-1"
        assert plan[0]["description"] == "Parse attachment: document.pdf"
        assert plan[1]["tool"] == "summarise"
        assert plan[1]["params"]["text"] == "Email with attachment"

    def test_fallback_plan_with_multiple_attachments(self):
        """Test that fallback plan handles multiple attachments correctly."""
        attachments = [
            Attachment(
                id="att-1",
                name="doc1.pdf",
                type="application/pdf",
                file_id="file-123",
            ),
            Attachment(
                id="att-2",
                name="doc2.xlsx",
                type="application/vnd.ms-excel",
                file_id="file-456",
            ),
            Attachment(
                id="att-3",
                name="doc3.docx",
                type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                file_id="file-789",
            ),
        ]
        email_data = EmailData(
            from_email="test@example.com",
            subject="Test Subject",
            text="Email with multiple attachments",
            attachments=attachments,
        )

        plan = _create_fallback_plan(email_data)

        # Should have 4 steps: 3 parse steps + 1 summarise
        assert len(plan) == 4
        assert plan[0]["tool"] == "parse"
        assert plan[0]["params"]["file_id"] == "att-1"
        assert plan[0]["description"] == "Parse attachment: doc1.pdf"
        assert plan[1]["tool"] == "parse"
        assert plan[1]["params"]["file_id"] == "att-2"
        assert plan[1]["description"] == "Parse attachment: doc2.xlsx"
        assert plan[2]["tool"] == "parse"
        assert plan[2]["params"]["file_id"] == "att-3"
        assert plan[2]["description"] == "Parse attachment: doc3.docx"
        assert plan[3]["tool"] == "summarise"

    def test_fallback_plan_attachment_with_content(self):
        """Test that fallback plan works with content-based attachments."""
        # Attachment with base64 content instead of file_id
        attachment = Attachment(
            id="content-id-1",
            name="document.pdf",
            type="application/pdf",
            content="base64content",  # Using content instead of file_id
        )
        email_data = EmailData(
            from_email="test@example.com",
            subject="Test Subject",
            text="Email with attachment",
            attachments=[attachment],
        )

        plan = _create_fallback_plan(email_data)

        # Should use the attachment id
        assert len(plan) == 2
        assert plan[0]["tool"] == "parse"
        assert plan[0]["params"]["file_id"] == "content-id-1"
        assert plan[0]["description"] == "Parse attachment: document.pdf"

    def test_fallback_plan_content_truncation(self):
        """Test that email content is truncated to 10000 characters."""
        # Create content longer than 10000 characters
        long_content = "A" * 12000
        email_data = EmailData(
            from_email="test@example.com",
            subject="Test Subject",
            text=long_content,
        )

        plan = _create_fallback_plan(email_data)

        # Content should be truncated to 10000 characters (new limit)
        assert len(plan) == 1
        assert plan[0]["tool"] == "summarise"
        assert len(plan[0]["params"]["text"]) == 10000
        assert plan[0]["params"]["text"] == "A" * 10000

    def test_fallback_plan_uses_html_when_text_missing(self):
        """Test that fallback plan uses HTML content when text is missing."""
        email_data = EmailData(
            from_email="test@example.com",
            subject="Test Subject",
            html="<p>This is HTML content</p>",
        )

        plan = _create_fallback_plan(email_data)

        assert len(plan) == 1
        assert plan[0]["tool"] == "summarise"
        assert plan[0]["params"]["text"] == "<p>This is HTML content</p>"

    def test_fallback_plan_uses_empty_when_no_content(self):
        """Test that fallback plan uses '(empty)' when no content is available."""
        email_data = EmailData(
            from_email="test@example.com",
            subject="Test Subject",
        )

        plan = _create_fallback_plan(email_data)

        assert len(plan) == 1
        assert plan[0]["tool"] == "summarise"
        assert plan[0]["params"]["text"] == "(empty)"

    def test_fallback_plan_splits_email_chain(self):
        """Test that fallback plan uses email splitting to separate top email from quoted chain."""
        email_body = """This is my request.

Please help with this task.

On Jan 1, 2024, someone@example.com wrote:
> This is the previous email
> with quoted content
> that continues for many lines""" + ("A" * 3000)  # Make it long enough
        
        email_data = EmailData(
            from_email="test@example.com",
            subject="Test",
            text=email_body,
        )

        plan = _create_fallback_plan(email_data)

        # Should have a summarise step
        assert len(plan) == 1
        assert plan[0]["tool"] == "summarise"
        
        # The text should be the top email, not the full body
        summarise_text = plan[0]["params"]["text"]
        assert "This is my request" in summarise_text
        assert "Please help with this task" in summarise_text
        
        # The quoted content should be largely absent or minimal
        # (it should be in the chain that was split off)
        # The summarise_text should be shorter than the original body
        assert len(summarise_text) < len(email_body)


class TestParsePlanFallback:
    """Tests to verify parse_plan correctly uses _create_fallback_plan."""

    def test_parse_plan_unparseable_response(self):
        """Test that unparseable LLM response triggers fallback plan."""
        email_data = EmailData(
            from_email="test@example.com",
            subject="Test",
            text="Test content",
        )

        # Invalid JSON that cannot be parsed
        response = "This is not valid JSON at all"
        plan = parse_plan(response, email_data)

        # Should return fallback plan
        assert len(plan) == 1
        assert plan[0]["tool"] == "summarise"
        assert plan[0]["params"]["text"] == "Test content"

    def test_parse_plan_invalid_json_exception(self):
        """Test that JSON parsing exception triggers fallback plan."""
        email_data = EmailData(
            from_email="test@example.com",
            subject="Test",
            text="Test content",
        )

        # Invalid JSON that raises exception during parsing
        response = "[{invalid json"
        plan = parse_plan(response, email_data)

        # Should return fallback plan
        assert len(plan) == 1
        assert plan[0]["tool"] == "summarise"

    def test_parse_plan_fallback_with_attachments(self):
        """Test that fallback plan includes attachments when LLM response is invalid."""
        attachment = Attachment(
            id="att-1",
            name="document.pdf",
            type="application/pdf",
            file_id="file-123",
        )
        email_data = EmailData(
            from_email="test@example.com",
            subject="Test",
            text="Test content",
            attachments=[attachment],
        )

        # Invalid response
        response = "Not valid JSON"
        plan = parse_plan(response, email_data)

        # Should return fallback plan with parse step for attachment
        assert len(plan) == 2
        assert plan[0]["tool"] == "parse"
        assert plan[0]["params"]["file_id"] == "att-1"
        assert plan[1]["tool"] == "summarise"

    def test_parse_plan_fallback_truncates_content(self):
        """Test that fallback plan correctly truncates long email content."""
        # Create content longer than 10000 characters
        long_content = "B" * 12000
        email_data = EmailData(
            from_email="test@example.com",
            subject="Test",
            text=long_content,
        )

        # Invalid response to trigger fallback
        response = "Invalid JSON"
        plan = parse_plan(response, email_data)

        # Content should be truncated in fallback plan to 10000 characters
        assert len(plan) == 1
        assert plan[0]["tool"] == "summarise"
        assert len(plan[0]["params"]["text"]) == 10000
        assert plan[0]["params"]["text"] == "B" * 10000

    def test_parse_plan_valid_json_does_not_use_fallback(self):
        """Test that valid JSON response does NOT trigger fallback plan."""
        email_data = EmailData(
            from_email="test@example.com",
            subject="Test",
            text="Test content",
        )

        # Valid JSON response
        response = """[
            {
                "tool": "custom_tool",
                "params": {"arg": "value"},
                "description": "Custom step"
            }
        ]"""
        plan = parse_plan(response, email_data)

        # Should NOT use fallback plan
        assert len(plan) == 1
        assert plan[0]["tool"] == "custom_tool"
        assert plan[0]["params"]["arg"] == "value"
