"""
Detailed analysis of the 31-W Insulation policy assignment failure.

Based on the test results, we've identified the root cause:
- Text extraction: ✅ Works (OCR extracts text successfully)
- Date pattern recognition: ✅ Works (finds 11/01/2023, 11/01/2024, 11/06/2023)
- Policy assignment logic: ❌ FAILS (assigns wrong dates to GL expiration)

The issue is in the naive policy assignment logic in pdf_parser.py lines 769-795.
The current logic assigns dates in chronological order without considering context.

Expected behavior:
- GL Effective: 2023-11-01 ✅ (correctly assigned)
- GL Expiration: 2024-11-01 ❌ (incorrectly assigned 2023-11-06 - the certificate date)
- WC dates should be different or None

Actual behavior:
- GL Effective: 2023-11-01 ✅
- GL Expiration: 2023-11-06 ❌ (this is the certificate issue date, not policy expiration)
- WC Effective: 2024-11-01 ❌ (this should be GL expiration)
- WC Expiration: None
"""

import pytest
import sys
import os
from pathlib import Path
from datetime import date
import re
from typing import List, Dict, Optional, Any

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.coi_auditor.pdf_parser import (
    extract_dates_from_pdf,
    extract_raw_ocr_text_from_pdf,
    _parse_date_string,
    DATE_PATTERNS
)

def test_31w_insulation_policy_assignment_bug():
    """
    Demonstrates the specific bug in policy assignment logic.
    
    The issue is that the current logic in pdf_parser.py (lines 769-795) uses a naive
    chronological assignment that doesn't distinguish between:
    1. Certificate issue date (11/06/2023)
    2. Policy effective date (11/01/2023) 
    3. Policy expiration date (11/01/2024)
    """
    pdf_path = Path("tests/fixtures/31-W Insulation_2023-11-06.pdf")
    
    # Extract text and verify it contains the expected dates
    notes = []
    extracted_text = extract_raw_ocr_text_from_pdf(pdf_path, notes)
    assert extracted_text is not None
    
    print("=== EXTRACTED TEXT ANALYSIS ===")
    print(f"Text length: {len(extracted_text)} characters")
    
    # Show context around each date to understand the layout
    dates_to_analyze = ["11/06/2023", "11/01/2023", "11/01/2024"]
    
    for date_str in dates_to_analyze:
        indices = []
        start = 0
        while True:
            idx = extracted_text.lower().find(date_str.lower(), start)
            if idx == -1:
                break
            indices.append(idx)
            start = idx + 1
        
        print(f"\nDate '{date_str}' found at {len(indices)} location(s):")
        for i, idx in enumerate(indices):
            context_start = max(0, idx - 100)
            context_end = min(len(extracted_text), idx + len(date_str) + 100)
            context = extracted_text[context_start:context_end].replace('\n', ' ')
            print(f"  Location {i+1}: ...{context}...")
    
    # Run the full extraction to see the current (buggy) behavior
    extracted_dates, extraction_notes = extract_dates_from_pdf(pdf_path, "31-W Insulation")
    
    print("\n=== CURRENT (BUGGY) EXTRACTION RESULTS ===")
    print(f"Extracted dates: {extracted_dates}")
    print(f"Notes: {extraction_notes}")
    
    # Analyze the specific bug
    print("\n=== BUG ANALYSIS ===")
    
    # The bug: GL expiration is assigned the certificate date instead of policy expiration
    gl_exp_actual = extracted_dates.get('gl_exp_date')
    certificate_date = date(2023, 11, 6)  # This is the certificate issue date
    policy_exp_date = date(2024, 11, 1)   # This should be the GL expiration
    
    print(f"GL Expiration (actual): {gl_exp_actual}")
    print(f"Certificate issue date: {certificate_date}")
    print(f"Expected policy expiration: {policy_exp_date}")
    
    # Demonstrate the bug
    bug_confirmed = (gl_exp_actual == certificate_date and 
                    gl_exp_actual != policy_exp_date)
    
    print(f"\nBUG CONFIRMED: {bug_confirmed}")
    if bug_confirmed:
        print("❌ The algorithm incorrectly assigned the certificate issue date")
        print("   (11/06/2023) as the GL expiration instead of the policy")
        print("   expiration date (11/01/2024)")
    
    # Show why this happens in the current logic
    print("\n=== WHY THE BUG OCCURS ===")
    print("Current logic in pdf_parser.py lines 769-795:")
    print("1. Finds all dates: [2023-11-01, 2023-11-06, 2024-11-01]")
    print("2. Assigns first date (2023-11-01) as GL effective ✅")
    print("3. Assigns next chronological date (2023-11-06) as GL expiration ❌")
    print("4. Assigns remaining date (2024-11-01) as WC effective ❌")
    print("\nThe logic doesn't understand that:")
    print("- 11/06/2023 is the certificate issue date (not a policy date)")
    print("- 11/01/2023 and 11/01/2024 are the actual policy effective/expiration pair")
    
    # Demonstrate what the correct assignment should be
    print("\n=== CORRECT ASSIGNMENT SHOULD BE ===")
    print("GL Effective: 2023-11-01 (earliest policy date)")
    print("GL Expiration: 2024-11-01 (latest policy date, exactly 1 year later)")
    print("WC Effective: None or different dates")
    print("WC Expiration: None or different dates")
    print("Certificate date (11/06/2023) should be ignored for policy dates")
    
    # This assertion will fail, demonstrating the bug
    assert gl_exp_actual == policy_exp_date, (
        f"BUG REPRODUCED: GL expiration incorrectly assigned to {gl_exp_actual} "
        f"(certificate date) instead of {policy_exp_date} (policy expiration)"
    )

def test_demonstrate_correct_date_pairing():
    """
    Demonstrates how the dates should be correctly paired based on context.
    
    In a COI certificate:
    - Certificate issue date appears near "DATE (MM/DD/YYYY)" header
    - Policy dates appear in the policy table rows
    - Policy effective and expiration dates are typically exactly 1 year apart
    """
    pdf_path = Path("tests/fixtures/31-W Insulation_2023-11-06.pdf")
    
    # Extract text
    notes = []
    extracted_text = extract_raw_ocr_text_from_pdf(pdf_path, notes)
    assert extracted_text is not None
    
    # Find all dates
    all_dates = []
    for pattern in DATE_PATTERNS:
        matches = re.findall(pattern, extracted_text, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple) and len(match) == 3:
                if len(match[2]) == 4:  # YYYY format
                    date_str = f"{match[0]}/{match[1]}/{match[2]}"
                    parsed_date = _parse_date_string(date_str, [])
                    if parsed_date and parsed_date not in all_dates:
                        all_dates.append(parsed_date)
    
    all_dates.sort()
    print(f"All found dates: {all_dates}")
    
    # Demonstrate correct pairing logic
    print("\n=== CORRECT PAIRING LOGIC ===")
    
    # Rule 1: Certificate date is usually close to current date and appears near "DATE" header
    certificate_candidates = []
    policy_candidates = []
    
    for d in all_dates:
        # Certificate dates are typically within a few days of when the certificate was issued
        # and appear near the "DATE (MM/DD/YYYY)" text
        if d.year == 2023 and d.month == 11 and d.day == 6:
            certificate_candidates.append(d)
        else:
            policy_candidates.append(d)
    
    print(f"Certificate date candidates: {certificate_candidates}")
    print(f"Policy date candidates: {policy_candidates}")
    
    # Rule 2: Policy dates are typically exactly 1 year apart
    if len(policy_candidates) >= 2:
        for i, date1 in enumerate(policy_candidates):
            for j, date2 in enumerate(policy_candidates[i+1:], i+1):
                days_diff = abs((date2 - date1).days)
                if 360 <= days_diff <= 370:  # Approximately 1 year
                    print(f"Found 1-year policy pair: {date1} to {date2} ({days_diff} days)")
                    print(f"This should be: GL Effective: {date1}, GL Expiration: {date2}")
    
    # Rule 3: Context analysis (simplified)
    print("\n=== CONTEXT ANALYSIS ===")
    
    # Look for "GENERAL LIABILITY" section
    gl_section_start = extracted_text.lower().find("general liability")
    if gl_section_start != -1:
        # Look for dates within 200 characters of "GENERAL LIABILITY"
        gl_context = extracted_text[gl_section_start:gl_section_start + 200]
        print(f"General Liability context: {gl_context.replace(chr(10), ' ')}")
        
        # Find dates in this context
        gl_dates_in_context = []
        for date_str in ["11/01/2023", "11/01/2024", "11/06/2023"]:
            if date_str in gl_context:
                gl_dates_in_context.append(date_str)
        
        print(f"Dates found in GL context: {gl_dates_in_context}")

if __name__ == "__main__":
    print("Running detailed analysis of 31-W Insulation policy assignment bug...")
    try:
        test_31w_insulation_policy_assignment_bug()
    except AssertionError as e:
        print(f"\n✅ BUG SUCCESSFULLY REPRODUCED: {e}")
    
    print("\n" + "="*60)
    test_demonstrate_correct_date_pairing()