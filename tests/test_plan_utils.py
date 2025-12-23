"""Tests for plan_utils module, specifically the _create_fallback_plan helper function."""

from basic.models import Attachment, EmailData
from basic.plan_utils import _create_fallback_plan, parse_plan, resolve_params


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


class TestResolveParams:
    """Tests for the resolve_params function."""

    def test_resolve_simple_string(self):
        """Test that simple strings are passed through unchanged."""
        params = {"text": "hello world", "count": "123"}
        context = {}
        email_data = EmailData(from_email="test@example.com", subject="Test")
        
        resolved = resolve_params(params, context, email_data)
        
        assert resolved["text"] == "hello world"
        assert resolved["count"] == "123"

    def test_resolve_dict_reference_single_brace(self):
        """Test that dict reference with single braces preserves the dict type."""
        params = {"data": "{step_1.extracted_data}"}
        context = {
            "step_1": {
                "extracted_data": {"x": [1, 2, 3], "y": [4, 5, 6]}
            }
        }
        email_data = EmailData(from_email="test@example.com", subject="Test")
        
        resolved = resolve_params(params, context, email_data)
        
        # Should preserve dict type, not convert to string
        assert isinstance(resolved["data"], dict)
        assert resolved["data"] == {"x": [1, 2, 3], "y": [4, 5, 6]}
        assert resolved["data"]["x"] == [1, 2, 3]
        assert resolved["data"]["y"] == [4, 5, 6]

    def test_resolve_dict_reference_double_brace(self):
        """Test that dict reference with double braces preserves the dict type."""
        params = {"data": "{{step_1.extracted_data}}"}
        context = {
            "step_1": {
                "extracted_data": {"values": [10, 20, 30], "labels": ["A", "B", "C"]}
            }
        }
        email_data = EmailData(from_email="test@example.com", subject="Test")
        
        resolved = resolve_params(params, context, email_data)
        
        # Should preserve dict type, not convert to string
        assert isinstance(resolved["data"], dict)
        assert resolved["data"] == {"values": [10, 20, 30], "labels": ["A", "B", "C"]}
        assert resolved["data"]["values"] == [10, 20, 30]
        assert resolved["data"]["labels"] == ["A", "B", "C"]

    def test_resolve_dict_reference_with_whitespace(self):
        """Test that dict reference with whitespace in double braces works."""
        params = {"data": "{{ step_1.extracted_data }}"}
        context = {
            "step_1": {
                "extracted_data": {"x": [1, 2], "y": [3, 4]}
            }
        }
        email_data = EmailData(from_email="test@example.com", subject="Test")
        
        resolved = resolve_params(params, context, email_data)
        
        # Should preserve dict type despite whitespace
        assert isinstance(resolved["data"], dict)
        assert resolved["data"] == {"x": [1, 2], "y": [3, 4]}

    def test_resolve_list_reference(self):
        """Test that list reference preserves the list type."""
        params = {"items": "{step_1.list_data}"}
        context = {
            "step_1": {
                "list_data": [1, 2, 3, 4, 5]
            }
        }
        email_data = EmailData(from_email="test@example.com", subject="Test")
        
        resolved = resolve_params(params, context, email_data)
        
        # Should preserve list type, not convert to string
        assert isinstance(resolved["items"], list)
        assert resolved["items"] == [1, 2, 3, 4, 5]

    def test_resolve_nested_dict_reference(self):
        """Test that nested dict reference preserves the dict structure."""
        params = {"result": "{step_1.nested_data}"}
        context = {
            "step_1": {
                "nested_data": {
                    "user": {"name": "John", "age": 30},
                    "scores": [85, 92, 78]
                }
            }
        }
        email_data = EmailData(from_email="test@example.com", subject="Test")
        
        resolved = resolve_params(params, context, email_data)
        
        # Should preserve nested structure
        assert isinstance(resolved["result"], dict)
        assert resolved["result"]["user"]["name"] == "John"
        assert resolved["result"]["scores"] == [85, 92, 78]

    def test_resolve_embedded_reference_converts_to_string(self):
        """Test that embedded references in strings are converted to strings."""
        params = {"message": "The count is {step_1.count} items"}
        context = {
            "step_1": {
                "count": 42
            }
        }
        email_data = EmailData(from_email="test@example.com", subject="Test")
        
        resolved = resolve_params(params, context, email_data)
        
        # Should convert to string when embedded in text
        assert isinstance(resolved["message"], str)
        assert resolved["message"] == "The count is 42 items"

    def test_resolve_embedded_dict_reference_converts_to_string(self):
        """Test that dict reference embedded in text is converted to string."""
        params = {"message": "Data: {step_1.data} end"}
        context = {
            "step_1": {
                "data": {"x": [1, 2], "y": [3, 4]}
            }
        }
        email_data = EmailData(from_email="test@example.com", subject="Test")
        
        resolved = resolve_params(params, context, email_data)
        
        # Should convert dict to string when embedded
        assert isinstance(resolved["message"], str)
        assert "{'x': [1, 2], 'y': [3, 4]}" in resolved["message"]

    def test_resolve_multiple_references_in_string(self):
        """Test that multiple references in a string are all resolved."""
        params = {"message": "Value1: {step_1.val1}, Value2: {step_2.val2}"}
        context = {
            "step_1": {"val1": "hello"},
            "step_2": {"val2": "world"}
        }
        email_data = EmailData(from_email="test@example.com", subject="Test")
        
        resolved = resolve_params(params, context, email_data)
        
        assert resolved["message"] == "Value1: hello, Value2: world"

    def test_resolve_nonexistent_reference_keeps_original(self):
        """Test that nonexistent references are kept as-is."""
        params = {"data": "{step_99.missing}"}
        context = {
            "step_1": {"value": "something"}
        }
        email_data = EmailData(from_email="test@example.com", subject="Test")
        
        resolved = resolve_params(params, context, email_data)
        
        # Should keep original value when reference not found
        assert resolved["data"] == "{step_99.missing}"

    def test_resolve_non_string_params_unchanged(self):
        """Test that non-string params are passed through unchanged."""
        params = {"count": 123, "flag": True, "data": {"key": "value"}}
        context = {}
        email_data = EmailData(from_email="test@example.com", subject="Test")
        
        resolved = resolve_params(params, context, email_data)
        
        assert resolved["count"] == 123
        assert resolved["flag"] is True
        assert resolved["data"] == {"key": "value"}

    def test_resolve_int_reference_preserves_type(self):
        """Test that int reference preserves the int type."""
        params = {"width": "{step_1.width}"}
        context = {
            "step_1": {"width": 10}
        }
        email_data = EmailData(from_email="test@example.com", subject="Test")
        
        resolved = resolve_params(params, context, email_data)
        
        # Should preserve int type
        assert isinstance(resolved["width"], int)
        assert resolved["width"] == 10

    def test_resolve_float_reference_preserves_type(self):
        """Test that float reference preserves the float type."""
        params = {"height": "{step_1.height}"}
        context = {
            "step_1": {"height": 6.5}
        }
        email_data = EmailData(from_email="test@example.com", subject="Test")
        
        resolved = resolve_params(params, context, email_data)
        
        # Should preserve float type
        assert isinstance(resolved["height"], float)
        assert resolved["height"] == 6.5

    def test_resolve_bool_reference_preserves_type(self):
        """Test that bool reference preserves the bool type."""
        params = {"flag": "{step_1.success}"}
        context = {
            "step_1": {"success": True}
        }
        email_data = EmailData(from_email="test@example.com", subject="Test")
        
        resolved = resolve_params(params, context, email_data)
        
        # Should preserve bool type
        assert isinstance(resolved["flag"], bool)
        assert resolved["flag"] is True

    def test_resolve_none_reference_preserves_type(self):
        """Test that None reference preserves None rather than converting to string."""
        params = {"data": "{step_1.result}"}
        context = {
            "step_1": {"result": None}
        }
        email_data = EmailData(from_email="test@example.com", subject="Test")
        
        resolved = resolve_params(params, context, email_data)
        
        # Should preserve None type, not convert to "None" string
        assert resolved["data"] is None
        assert not isinstance(resolved["data"], str)

    def test_resolve_empty_dict_preserves_type(self):
        """Test that empty dict reference preserves the empty dict."""
        params = {"data": "{step_1.empty_dict}"}
        context = {
            "step_1": {"empty_dict": {}}
        }
        email_data = EmailData(from_email="test@example.com", subject="Test")
        
        resolved = resolve_params(params, context, email_data)
        
        # Should preserve empty dict, not convert to string
        assert isinstance(resolved["data"], dict)
        assert resolved["data"] == {}
        assert len(resolved["data"]) == 0

    def test_resolve_empty_list_preserves_type(self):
        """Test that empty list reference preserves the empty list."""
        params = {"items": "{step_1.empty_list}"}
        context = {
            "step_1": {"empty_list": []}
        }
        email_data = EmailData(from_email="test@example.com", subject="Test")
        
        resolved = resolve_params(params, context, email_data)
        
        # Should preserve empty list, not convert to string
        assert isinstance(resolved["items"], list)
        assert resolved["items"] == []
        assert len(resolved["items"]) == 0

    def test_resolve_malformed_extra_braces(self):
        """Test that malformed references with extra braces are handled safely."""
        params = {"data": "{{{step_1.field}}}"}
        context = {
            "step_1": {"field": "value"}
        }
        email_data = EmailData(from_email="test@example.com", subject="Test")
        
        resolved = resolve_params(params, context, email_data)
        
        # The pattern matches the inner reference and substitutes it
        # Result: {{{ becomes {{, {step_1.field} gets substituted, }}} becomes }}
        assert resolved["data"] == "{{value}}"

    def test_resolve_malformed_semicolon_injection(self):
        """Test that references with semicolons or injection attempts are handled safely."""
        params = {"data": "{{step_1.field; malicious}}"}
        context = {
            "step_1": {"field": "value"}
        }
        email_data = EmailData(from_email="test@example.com", subject="Test")
        
        resolved = resolve_params(params, context, email_data)
        
        # Should keep original value since field name contains invalid characters
        assert resolved["data"] == "{{step_1.field; malicious}}"

    def test_resolve_malformed_nested_fields(self):
        """Test that nested field references are not supported and handled gracefully."""
        params = {"data": "{step_1.nested.field}"}
        context = {
            "step_1": {"nested": {"field": "value"}}
        }
        email_data = EmailData(from_email="test@example.com", subject="Test")
        
        resolved = resolve_params(params, context, email_data)
        
        # Should keep original value since nested fields are not supported
        # The pattern doesn't match multi-level nesting
        assert resolved["data"] == "{step_1.nested.field}"

