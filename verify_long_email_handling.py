#!/usr/bin/env python3
"""Manual verification script for long email handling in workflow."""

import sys
sys.path.insert(0, 'src')


def test_prompt_building():
    """Test that prompt building handles long emails correctly."""
    from basic.models import EmailData
    from basic.prompt_utils import build_triage_prompt
    
    print("\n" + "="*60)
    print("Test 1: Long email without quoted content")
    print("="*60)
    
    # Create a long email (more than old 5000 char limit)
    long_body = "This is important content that should not be truncated. " * 200  # ~11,200 chars
    
    email_data = EmailData(
        from_email="user@example.com",
        subject="Important Request",
        text=long_body,
    )
    
    prompt = build_triage_prompt(
        email_data,
        tool_descriptions="[Tools descriptions here]",
        response_best_practices="[Best practices here]",
    )
    
    # Check that content is included beyond 5000 chars
    content_count = prompt.count("This is important content")
    print(f"Content phrase appears {content_count} times in prompt")
    
    if content_count > 89:  # 5000 chars / 56 chars per phrase ≈ 89
        print("✅ PASS: Content extends beyond old 5000 char limit")
    else:
        print("❌ FAIL: Content seems truncated at old limit")
        return False
    
    print("\n" + "="*60)
    print("Test 2: Email with quoted chain")
    print("="*60)
    
    email_with_chain = """Please help me with this urgent task.

I need this done ASAP.

On Mon, Jan 15, 2024, John Doe <john@example.com> wrote:
> This is the previous email
> with quoted content
> that goes on for many lines
> and continues here
> with more information""" + ("X" * 1000)  # Add more content to chain
    
    email_data = EmailData(
        from_email="user@example.com",
        subject="Urgent Task",
        text=email_with_chain,
    )
    
    # Build prompt with email chain file
    prompt = build_triage_prompt(
        email_data,
        tool_descriptions="[Tools descriptions here]",
        response_best_practices="[Best practices here]",
        email_chain_file="email_chain.md",
    )
    
    # Check that top email is in prompt
    if "Please help me with this urgent task" in prompt:
        print("✅ Top email content is in prompt")
    else:
        print("❌ FAIL: Top email content missing")
        return False
    
    # Check that email chain file is referenced
    if "email_chain.md" in prompt:
        print("✅ Email chain file is referenced in prompt")
    else:
        print("❌ FAIL: Email chain file not referenced")
        return False
    
    # Check that quoted content is NOT in prompt
    if "This is the previous email" not in prompt:
        print("✅ Quoted content is not in prompt (correctly separated)")
    else:
        print("❌ FAIL: Quoted content should not be in prompt")
        return False
    
    print("\n" + "="*60)
    print("Test 3: Very long email (>10k chars) gets truncation note")
    print("="*60)
    
    very_long = "Y" * 15000
    
    email_data = EmailData(
        from_email="user@example.com",
        subject="Very Long Email",
        text=very_long,
    )
    
    prompt = build_triage_prompt(
        email_data,
        tool_descriptions="[Tools]",
        response_best_practices="[Practices]",
    )
    
    if "Email truncated - content exceeds length limit" in prompt:
        print("✅ PASS: Truncation note present for very long email")
    else:
        print("❌ FAIL: Missing truncation note")
        return False
    
    print("\n" + "="*60)
    print("Test 4: Fallback plan uses email splitting")
    print("="*60)
    
    from basic.plan_utils import _create_fallback_plan
    
    email_body = """My new request here.

On Jan 1, 2024, someone wrote:
> Old message
> More old content""" + ("A" * 6000)  # Make it long
    
    email_data = EmailData(
        from_email="user@example.com",
        subject="Test",
        text=email_body,
    )
    
    plan = _create_fallback_plan(email_data)
    
    if len(plan) == 1 and plan[0]["tool"] == "summarise":
        text_to_summarise = plan[0]["params"]["text"]
        if "My new request here" in text_to_summarise:
            print("✅ PASS: Fallback plan includes top email")
            # Length check - should be shorter than full body due to splitting
            if len(text_to_summarise) < len(email_body):
                print("✅ PASS: Text is shorter (chain was split off)")
            else:
                print("⚠️  WARNING: Text length not reduced by splitting")
        else:
            print("❌ FAIL: Top email content missing from fallback plan")
            return False
    else:
        print("❌ FAIL: Unexpected fallback plan structure")
        return False
    
    return True


def main():
    """Run all verification tests."""
    print("Long Email Handling Verification")
    print("="*60)
    
    try:
        success = test_prompt_building()
        
        if success:
            print("\n" + "="*60)
            print("✅ All manual verification tests passed!")
            print("="*60)
            return 0
        else:
            print("\n" + "="*60)
            print("❌ Some verification tests failed")
            print("="*60)
            return 1
    except Exception as e:
        print(f"\n❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
