#!/usr/bin/env python3
"""Verification script for workflow not responding fix.

This script verifies that workflow step methods have proper type annotations
after removing the @observe decorator, ensuring the workflow can properly
route events between steps.
"""

import ast
import inspect
from pathlib import Path


def check_file_step_annotations(filepath: Path) -> dict:
    """Check that all workflow step methods have proper type annotations.
    
    Args:
        filepath: Path to the Python file to check
        
    Returns:
        Dictionary with check results
    """
    results = {
        "file": str(filepath),
        "steps_found": [],
        "steps_with_annotations": [],
        "steps_without_annotations": [],
        "has_observe_decorator": [],
    }
    
    with open(filepath, "r") as f:
        source = f.read()
    
    tree = ast.parse(source)
    
    # Find all Workflow classes
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Check if this is a Workflow class (by looking for 'Workflow' in bases)
            is_workflow = any(
                (isinstance(base, ast.Name) and base.id == "Workflow") or
                (isinstance(base, ast.Attribute) and base.attr == "Workflow")
                for base in node.bases
            )
            
            if not is_workflow:
                continue
                
            # Check all methods in this class
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_name = item.name
                    
                    # Check if method has @step decorator
                    has_step_decorator = any(
                        (isinstance(dec, ast.Name) and dec.id == "step") or
                        (isinstance(dec, ast.Attribute) and dec.attr == "step")
                        for dec in item.decorator_list
                    )
                    
                    if not has_step_decorator:
                        continue
                    
                    # This is a step method
                    results["steps_found"].append(method_name)
                    
                    # Check if it has @observe decorator
                    has_observe = any(
                        (isinstance(dec, ast.Name) and dec.id == "observe") or
                        (isinstance(dec, ast.Call) and 
                         isinstance(dec.func, ast.Name) and dec.func.id == "observe")
                        for dec in item.decorator_list
                    )
                    
                    if has_observe:
                        results["has_observe_decorator"].append(method_name)
                    
                    # Check if it has return type annotation
                    if item.returns:
                        return_type = ast.unparse(item.returns)
                        results["steps_with_annotations"].append({
                            "method": method_name,
                            "return_type": return_type
                        })
                    else:
                        results["steps_without_annotations"].append(method_name)
    
    return results


def print_results(results: dict):
    """Print check results in a readable format."""
    print(f"\n{'='*70}")
    print(f"File: {results['file']}")
    print(f"{'='*70}")
    
    print(f"\n✓ Steps found: {len(results['steps_found'])}")
    for step in results['steps_found']:
        print(f"  - {step}")
    
    if results['has_observe_decorator']:
        print(f"\n⚠ Steps with @observe decorator: {len(results['has_observe_decorator'])}")
        for step in results['has_observe_decorator']:
            print(f"  - {step}")
    else:
        print(f"\n✓ No @observe decorators found (correct!)")
    
    if results['steps_without_annotations']:
        print(f"\n✗ Steps without return annotations: {len(results['steps_without_annotations'])}")
        for step in results['steps_without_annotations']:
            print(f"  - {step}")
    else:
        print(f"\n✓ All steps have return type annotations")
    
    if results['steps_with_annotations']:
        print(f"\n✓ Steps with proper annotations: {len(results['steps_with_annotations'])}")
        for step_info in results['steps_with_annotations']:
            print(f"  - {step_info['method']}: {step_info['return_type']}")


def main():
    """Run verification checks."""
    print("\n" + "="*70)
    print("Workflow Step Annotation Verification")
    print("Checking that @observe decorator has been removed and")
    print("type annotations are preserved for proper event routing")
    print("="*70)
    
    # Get project root
    script_dir = Path(__file__).parent
    project_root = script_dir
    
    # Files to check
    workflow_files = [
        project_root / "src" / "basic" / "email_workflow.py",
        project_root / "src" / "basic" / "workflow.py",
    ]
    
    all_passed = True
    
    for filepath in workflow_files:
        if not filepath.exists():
            print(f"\n✗ File not found: {filepath}")
            all_passed = False
            continue
        
        results = check_file_step_annotations(filepath)
        print_results(results)
        
        # Check for issues
        if results['has_observe_decorator']:
            print(f"\n⚠ ISSUE: File still has @observe decorators on workflow steps!")
            all_passed = False
        
        if results['steps_without_annotations']:
            print(f"\n⚠ ISSUE: Some steps are missing return type annotations!")
            all_passed = False
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    if all_passed:
        print("✓ All checks passed!")
        print("  - No @observe decorators on workflow steps")
        print("  - All steps have proper return type annotations")
        print("  - Workflow event routing should work correctly")
    else:
        print("✗ Some checks failed - see details above")
    
    return all_passed


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
