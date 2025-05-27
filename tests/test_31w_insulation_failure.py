"""
Minimal reproducible test case to isolate the "31-W Insulation Company" data extraction failure.

This test focuses on the specific PDF: tests/fixtures/31-W Insulation_2023-11-06.pdf
which should correspond to the certificate with dates "11/01/2023" to "11/01/2024".

The test isolates each step of the pipeline to identify where the failure occurs:
1. Text extraction quality
2. Date pattern recognition  
3. Policy assignment logic
4. Data propagation to Excel
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
    DATE_PATTERNS,
    POLICY_KEYWORDS,
    DATE_ROLE_KEYWORDS
)
from src.coi_auditor.config import load_config

class Test31WInsulationFailure:
    """Test class for isolating the 31-W Insulation data extraction failure."""
    
    @classmethod
    def setup_class(cls):
        """Set up test fixtures and expected data."""
        cls.config = load_config()
        cls.pdf_path = Path("tests/fixtures/31-W Insulation_2023-11-06.pdf")
        cls.expected_dates = {
            'gl_eff_date': date(2023, 11, 1),  # 11/01/2023
            'gl_exp_date': date(2024, 11, 1),  # 11/01/2024
        }
        cls.expected_date_strings = ["11/01/2023", "11/01/2024"]
        
        # Verify PDF exists
        assert cls.pdf_path.exists(), f"Test PDF not found: {cls.pdf_path}"
        
    def test_hypothesis_1_text_extraction_quality(self):
        """
        Hypothesis 1: Text extraction works but dates aren't found by regex.
        
        Tests:
        - PDF text extraction succeeds
        - Extracted text contains expected date strings
        """
        print(f"\n=== HYPOTHESIS 1: Text Extraction Quality ===")
        
        # Test text extraction
        notes = []
        extracted_text = extract_raw_ocr_text_from_pdf(self.pdf_path, notes)
        
        print(f"Text extraction notes: {notes}")
        assert extracted_text is not None, "Text extraction failed"
        assert len(extracted_text.strip()) > 0, "Extracted text is empty"
        
        print(f"Extracted text length: {len(extracted_text)} characters")
        print(f"First 500 characters:\n{extracted_text[:500]}")
        
        # Check if expected date strings are present in extracted text
        text_lower = extracted_text.lower()
        
        for expected_date_str in self.expected_date_strings:
            # Check various formats the date might appear in
            date_variants = [
                expected_date_str,  # 11/01/2023
                expected_date_str.replace("/0", "/"),  # 11/1/2023
                expected_date_str.replace("11/01/", "11/1/"),  # 11/1/2023
                expected_date_str.replace("/01/", "/1/"),  # 11/1/2023
            ]
            
            found_variant = None
            for variant in date_variants:
                if variant.lower() in text_lower:
                    found_variant = variant
                    break
                    
            print(f"Expected date '{expected_date_str}' - Found variant: {found_variant}")
            
            # For debugging, show context around where dates might be
            if found_variant:
                idx = text_lower.find(found_variant.lower())
                context_start = max(0, idx - 50)
                context_end = min(len(extracted_text), idx + len(found_variant) + 50)
                context = extracted_text[context_start:context_end]
                print(f"Context around '{found_variant}': ...{context}...")
        
        # This assertion might fail - that's the point of the test
        dates_found_in_text = any(
            any(variant.lower() in text_lower for variant in [
                date_str, 
                date_str.replace("/0", "/"),
                date_str.replace("11/01/", "11/1/"),
                date_str.replace("/01/", "/1/")
            ])
            for date_str in self.expected_date_strings
        )
        
        print(f"Expected dates found in extracted text: {dates_found_in_text}")
        
        # Don't assert here - we want to see what happens in the next steps
        return extracted_text, dates_found_in_text
    
    def test_hypothesis_2_date_pattern_recognition(self):
        """
        Hypothesis 2: Dates are found but assigned to wrong policy type.
        
        Tests:
        - Regex patterns find the expected dates
        - Date parsing succeeds
        """
        print(f"\n=== HYPOTHESIS 2: Date Pattern Recognition ===")
        
        # Get extracted text from previous test
        notes = []
        extracted_text = extract_raw_ocr_text_from_pdf(self.pdf_path, notes)
        assert extracted_text is not None
        
        # Test each regex pattern individually
        found_date_strings = []
        
        print(f"Testing {len(DATE_PATTERNS)} regex patterns:")
        for i, pattern in enumerate(DATE_PATTERNS):
            try:
                matches = re.findall(pattern, extracted_text, re.IGNORECASE)
                print(f"Pattern {i+1}: {pattern}")
                print(f"  Matches: {matches}")
                
                for match in matches:
                    if isinstance(match, tuple):
                        # Reconstruct date string from tuple groups
                        if len(match) == 3 and all(str(m).isdigit() for m in match):
                            if len(str(match[2])) == 4:  # YYYY format
                                date_str_candidate = f"{match[0]}/{match[1]}/{match[2]}"
                            elif len(str(match[2])) == 2:  # YY format
                                date_str_candidate = f"{match[0]}/{match[1]}/{match[2]}"
                            else:
                                continue
                            found_date_strings.append(date_str_candidate)
                            print(f"  Reconstructed: {date_str_candidate}")
                    elif isinstance(match, str):
                        found_date_strings.append(match)
                        print(f"  String match: {match}")
                        
            except re.error as e:
                print(f"  Regex error: {e}")
                continue
        
        # Test broader date phrase detection
        potential_date_phrases = re.findall(
            r'\b(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,)?\s+\d{2,4}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?(?:,)?\s+\d{2,4}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b',
            extracted_text,
            re.IGNORECASE
        )
        found_date_strings.extend(potential_date_phrases)
        
        print(f"\nBroader date phrase matches: {potential_date_phrases}")
        
        # Deduplicate
        unique_date_strings = sorted(list(set(found_date_strings)), key=len, reverse=True)
        print(f"\nUnique date strings found: {unique_date_strings}")
        
        # Test date parsing
        parsed_dates = []
        parsing_notes = []
        
        print(f"\nTesting date parsing:")
        for date_str in unique_date_strings:
            parsed_date = _parse_date_string(date_str, parsing_notes)
            if parsed_date:
                parsed_dates.append(parsed_date)
                print(f"  '{date_str}' -> {parsed_date}")
            else:
                print(f"  '{date_str}' -> FAILED")
        
        print(f"\nParsing notes: {parsing_notes}")
        print(f"Successfully parsed dates: {sorted(parsed_dates)}")
        
        # Check if expected dates were found and parsed
        expected_parsed_dates = [self.expected_dates['gl_eff_date'], self.expected_dates['gl_exp_date']]
        dates_correctly_parsed = all(exp_date in parsed_dates for exp_date in expected_parsed_dates)
        
        print(f"Expected dates correctly parsed: {dates_correctly_parsed}")
        print(f"Expected: {expected_parsed_dates}")
        print(f"Found: {parsed_dates}")
        
        return unique_date_strings, parsed_dates, dates_correctly_parsed
    
    def test_hypothesis_3_policy_assignment_logic(self):
        """
        Hypothesis 3: Dates are found and assigned correctly but not propagated to Excel.
        
        Tests:
        - Policy assignment logic
        - GL vs WC date assignment
        """
        print(f"\n=== HYPOTHESIS 3: Policy Assignment Logic ===")
        
        # Run the full extraction pipeline
        extracted_dates, notes = extract_dates_from_pdf(self.pdf_path, "31-W Insulation")
        
        print(f"Full extraction results:")
        print(f"  Extracted dates: {extracted_dates}")
        print(f"  Notes: {notes}")
        
        # Check if GL dates were assigned correctly
        gl_eff_correct = extracted_dates.get('gl_eff_date') == self.expected_dates['gl_eff_date']
        gl_exp_correct = extracted_dates.get('gl_exp_date') == self.expected_dates['gl_exp_date']
        
        print(f"\nGL Effective Date Assignment:")
        print(f"  Expected: {self.expected_dates['gl_eff_date']}")
        print(f"  Actual: {extracted_dates.get('gl_eff_date')}")
        print(f"  Correct: {gl_eff_correct}")
        
        print(f"\nGL Expiration Date Assignment:")
        print(f"  Expected: {self.expected_dates['gl_exp_date']}")
        print(f"  Actual: {extracted_dates.get('gl_exp_date')}")
        print(f"  Correct: {gl_exp_correct}")
        
        # Check WC assignments (should be None or different dates)
        wc_eff = extracted_dates.get('wc_eff_date')
        wc_exp = extracted_dates.get('wc_exp_date')
        
        print(f"\nWC Date Assignments:")
        print(f"  WC Effective: {wc_eff}")
        print(f"  WC Expiration: {wc_exp}")
        
        # Analyze the assignment logic
        print(f"\nAssignment Logic Analysis:")
        if not gl_eff_correct or not gl_exp_correct:
            print("  ❌ GL dates not assigned correctly")
            if wc_eff == self.expected_dates['gl_eff_date'] or wc_exp == self.expected_dates['gl_exp_date']:
                print("  ⚠️  Expected GL dates were assigned to WC instead")
            elif not extracted_dates.get('gl_eff_date') and not extracted_dates.get('gl_exp_date'):
                print("  ⚠️  No GL dates assigned at all")
            else:
                print("  ⚠️  GL dates assigned to unexpected values")
        else:
            print("  ✅ GL dates assigned correctly")
        
        return extracted_dates, gl_eff_correct and gl_exp_correct
    
    def test_comprehensive_pipeline_analysis(self):
        """
        Comprehensive test that runs all hypotheses and provides a summary.
        """
        print(f"\n" + "="*60)
        print(f"COMPREHENSIVE PIPELINE ANALYSIS: 31-W Insulation")
        print(f"PDF: {self.pdf_path}")
        print(f"Expected GL Effective: {self.expected_dates['gl_eff_date']}")
        print(f"Expected GL Expiration: {self.expected_dates['gl_exp_date']}")
        print(f"="*60)
        
        # Run all hypothesis tests
        try:
            extracted_text, text_has_dates = self.test_hypothesis_1_text_extraction_quality()
        except Exception as e:
            print(f"Hypothesis 1 failed with exception: {e}")
            text_has_dates = False
            
        try:
            date_strings, parsed_dates, dates_parsed = self.test_hypothesis_2_date_pattern_recognition()
        except Exception as e:
            print(f"Hypothesis 2 failed with exception: {e}")
            dates_parsed = False
            
        try:
            final_dates, assignment_correct = self.test_hypothesis_3_policy_assignment_logic()
        except Exception as e:
            print(f"Hypothesis 3 failed with exception: {e}")
            assignment_correct = False
            final_dates = {}
        
        # Summary
        print(f"\n" + "="*60)
        print(f"FAILURE ANALYSIS SUMMARY")
        print(f"="*60)
        print(f"1. Text Extraction Contains Expected Dates: {'✅' if text_has_dates else '❌'}")
        print(f"2. Date Pattern Recognition Works: {'✅' if dates_parsed else '❌'}")
        print(f"3. Policy Assignment Logic Correct: {'✅' if assignment_correct else '❌'}")
        
        print(f"\nFinal Extracted Dates:")
        for key, value in final_dates.items():
            expected_value = self.expected_dates.get(key.replace('_date', '_date'))
            status = "✅" if value == expected_value else "❌"
            print(f"  {key}: {value} {status}")
        
        # Determine root cause
        print(f"\nROOT CAUSE ANALYSIS:")
        if not text_has_dates:
            print("🔍 PRIMARY ISSUE: Text extraction doesn't contain expected dates")
            print("   - PDF may be image-based requiring OCR")
            print("   - Dates may be in different format than expected")
            print("   - Text extraction may be failing")
        elif not dates_parsed:
            print("🔍 PRIMARY ISSUE: Date pattern recognition failing")
            print("   - Regex patterns don't match the date format in PDF")
            print("   - Date parsing logic has issues")
        elif not assignment_correct:
            print("🔍 PRIMARY ISSUE: Policy assignment logic failing")
            print("   - Dates found but assigned to wrong policy type")
            print("   - Assignment heuristics are too naive")
            print("   - Need better contextual analysis")
        else:
            print("🔍 UNEXPECTED: All steps seem to work - check Excel propagation")
        
        print(f"="*60)
        
        # This test should fail to demonstrate the issue
        assert assignment_correct, f"31-W Insulation date extraction failed. Final dates: {final_dates}"

def test_31w_insulation_minimal_reproduction():
    """
    Minimal test function that can be run with pytest to reproduce the issue.
    """
    test_instance = Test31WInsulationFailure()
    test_instance.setup_class()
    test_instance.test_comprehensive_pipeline_analysis()

if __name__ == "__main__":
    # Run the test when executed directly
    test_instance = Test31WInsulationFailure()
    test_instance.setup_class()
    test_instance.test_comprehensive_pipeline_analysis()