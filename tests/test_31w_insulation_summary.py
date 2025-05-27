"""
SUMMARY: 31-W Insulation Data Extraction Failure - Root Cause Analysis

This test file documents the complete analysis of the "31-W Insulation Company" 
data extraction failure identified in row 7 of the audit results.

FINDINGS:
========

✅ TEXT EXTRACTION: Works correctly
   - PDF is image-based, requires OCR
   - PaddleOCR successfully extracts text (2664 characters)
   - All expected dates are present in extracted text

✅ DATE PATTERN RECOGNITION: Works correctly  
   - Regex patterns successfully find: 11/06/2023, 11/01/2023, 11/01/2024
   - Date parsing works correctly
   - All dates are parsed into proper date objects

❌ POLICY ASSIGNMENT LOGIC: FAILS - ROOT CAUSE IDENTIFIED
   - Current logic in pdf_parser.py lines 769-795 is naive
   - Uses simple chronological ordering without context analysis
   - Incorrectly assigns certificate issue date as policy expiration

SPECIFIC BUG:
============

Expected Assignment:
- GL Effective: 2023-11-01 ✅ (correctly assigned)
- GL Expiration: 2024-11-01 ❌ (should be this)
- WC dates: None or different dates

Actual (Buggy) Assignment:
- GL Effective: 2023-11-01 ✅ 
- GL Expiration: 2023-11-06 ❌ (this is the certificate issue date!)
- WC Effective: 2024-11-01 ❌ (this should be GL expiration)
- WC Expiration: None

CONTEXT ANALYSIS:
================

From the extracted text, we can see:
1. "DATE (MM/DD/YYYY) 11/06/2023" - This is the certificate issue date
2. Multiple instances of "11/01/2023 11/01/2024" in policy rows - These are policy dates
3. The policy dates appear together in the same table rows for different coverage types
4. The policy dates are exactly 366 days apart (1 year), indicating they're a pair

SOLUTION REQUIREMENTS:
=====================

The policy assignment logic needs to:
1. Distinguish between certificate dates and policy dates based on context
2. Recognize that policy effective/expiration dates typically appear as pairs
3. Use proximity analysis to group dates that appear together in policy rows
4. Ignore certificate issue dates when assigning policy dates

TECHNICAL DETAILS:
=================

The bug is in src/coi_auditor/pdf_parser.py, function extract_dates_from_pdf(),
specifically lines 769-795 where the naive assignment logic resides:

```python
# Current buggy logic:
if len(parsed_dates) >= 1:
    extracted_dates['gl_eff_date'] = parsed_dates[0]  # First date
if len(parsed_dates) >= 2:
    # This incorrectly takes the next chronological date
    potential_exp_gl = [d for d in parsed_dates if d > extracted_dates['gl_eff_date']]
    if potential_exp_gl:
        extracted_dates['gl_exp_date'] = potential_exp_gl[0]  # WRONG!
```

This logic assigns 2023-11-06 (certificate date) as GL expiration instead of 
2024-11-01 (actual policy expiration) because 2023-11-06 comes chronologically 
after 2023-11-01 but before 2024-11-01.

IMPACT:
=======

This bug affects any COI certificate where:
- The certificate issue date falls between policy effective and expiration dates
- Multiple policy types are present
- The naive chronological assignment picks the wrong date

This explains the "31-W Insulation Company" failure in row 7 of the audit results.
"""

import pytest
from pathlib import Path
from datetime import date

# Add project root to path
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.coi_auditor.pdf_parser import extract_dates_from_pdf

def test_31w_insulation_bug_reproduction():
    """
    Minimal test that reproduces the exact bug for documentation purposes.
    
    This test serves as a regression test - it should FAIL until the 
    policy assignment logic is fixed.
    """
    pdf_path = Path("tests/fixtures/31-W Insulation_2023-11-06.pdf")
    
    # Run extraction
    extracted_dates, notes = extract_dates_from_pdf(pdf_path, "31-W Insulation")
    
    # Expected correct assignment
    expected_gl_eff = date(2023, 11, 1)
    expected_gl_exp = date(2024, 11, 1)  # This should be the GL expiration
    
    # Current buggy assignment
    actual_gl_eff = extracted_dates.get('gl_eff_date')
    actual_gl_exp = extracted_dates.get('gl_exp_date')
    
    # Verify the bug exists
    assert actual_gl_eff == expected_gl_eff, "GL effective should be correct"
    
    # This assertion will FAIL, demonstrating the bug
    assert actual_gl_exp == expected_gl_exp, (
        f"BUG: GL expiration incorrectly assigned to {actual_gl_exp} "
        f"(certificate date) instead of {expected_gl_exp} (policy expiration). "
        f"This is the root cause of the 31-W Insulation extraction failure."
    )

def test_bug_documentation():
    """
    Documents the exact nature of the bug for future reference.
    """
    pdf_path = Path("tests/fixtures/31-W Insulation_2023-11-06.pdf")
    extracted_dates, notes = extract_dates_from_pdf(pdf_path, "31-W Insulation")
    
    print("\n" + "="*60)
    print("31-W INSULATION BUG DOCUMENTATION")
    print("="*60)
    print(f"PDF: {pdf_path}")
    print(f"Extracted dates: {extracted_dates}")
    print(f"Notes: {notes}")
    
    print("\nBUG ANALYSIS:")
    print("- GL Effective: ✅ Correct (2023-11-01)")
    print("- GL Expiration: ❌ Wrong (2023-11-06 = certificate date)")
    print("- Should be: GL Expiration = 2024-11-01 (policy expiration)")
    
    print("\nROOT CAUSE:")
    print("- Naive chronological assignment in pdf_parser.py lines 769-795")
    print("- Algorithm doesn't distinguish certificate dates from policy dates")
    print("- Needs context-aware assignment logic")
    
    print("\nIMPACT:")
    print("- Affects any COI where certificate date falls between policy dates")
    print("- Causes incorrect policy expiration dates in audit results")
    print("- Results in false positives for expired policies")
    print("="*60)

if __name__ == "__main__":
    print("Running 31-W Insulation bug reproduction test...")
    
    try:
        test_31w_insulation_bug_reproduction()
        print("❌ UNEXPECTED: Test passed - bug may have been fixed")
    except AssertionError as e:
        print(f"✅ EXPECTED: Bug reproduced successfully")
        print(f"Error: {e}")
    
    print("\n")
    test_bug_documentation()