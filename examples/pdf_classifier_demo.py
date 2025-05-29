"""
Demonstration of the PDF Classifier System

This script shows how to use the new PDF classification system to categorize
subcontractors based on their PDF status and evidence.
"""

import sys
import os
from pathlib import Path

# Add the src directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from coi_auditor.pdf_classifier import (
    classify_pdf_status,
    generate_diagnostic_record,
    get_classification_summary,
    PDFState,
    is_administrative_entry
)

def demo_classification():
    """Demonstrate the PDF classification system with various test cases."""
    
    print("=== PDF Classification System Demo ===\n")
    
    # Sample configuration
    config = {
        'fuzzy_matching': {
            'enabled': True,
            'threshold': 80
        }
    }
    
    # Test cases representing different scenarios
    test_cases = [
        {
            'name': 'ABC Construction LLC',
            'id': '001',
            'description': 'Normal business subcontractor'
        },
        {
            'name': 'TOTAL',
            'id': '999',
            'description': 'Administrative entry (should be skipped)'
        },
        {
            'name': 'XYZ Roofing Inc',
            'id': '002', 
            'description': 'Another business subcontractor'
        },
        {
            'name': 'Sub-Total',
            'id': '998',
            'description': 'Another administrative entry'
        },
        {
            'name': '   ',
            'id': '997',
            'description': 'Empty/whitespace entry'
        },
        {
            'name': 'Smith & Jones Plumbing',
            'id': '003',
            'description': 'Business with ampersand'
        }
    ]
    
    # Use a temporary directory for PDF search (won't find any PDFs)
    pdf_directory = "/tmp/nonexistent"
    
    print("Testing classification for various subcontractor types:\n")
    
    for i, case in enumerate(test_cases, 1):
        subcontractor = {
            'name': case['name'],
            'id': case['id']
        }
        
        print(f"{i}. {case['description']}")
        print(f"   Name: '{case['name']}'")
        
        # Quick administrative check
        is_admin = is_administrative_entry(case['name'])
        print(f"   Administrative: {is_admin}")
        
        # Full classification
        result = classify_pdf_status(subcontractor, pdf_directory, config)
        
        print(f"   State: {result['state']}")
        print(f"   Confidence: {result['confidence']:.1%}")
        print(f"   Action: {result['action']}")
        print(f"   Report Destination: {result['report_destination']}")
        
        # Generate summary
        summary = get_classification_summary(result)
        print(f"   Summary: {summary}")
        
        # For non-verified cases, show diagnostic info
        if result['state'] != PDFState.VERIFIED:
            diagnostic = generate_diagnostic_record(
                subcontractor, 
                result['state'], 
                result['confidence'], 
                result['evidence'], 
                result['action']
            )
            
            if diagnostic['manual_review_hints']:
                print(f"   Hints: {'; '.join(diagnostic['manual_review_hints'])}")
        
        print()

def demo_name_variations():
    """Demonstrate name variation generation for fuzzy matching."""
    
    print("=== Name Variation Generation Demo ===\n")
    
    from coi_auditor.pdf_classifier import generate_name_variations
    
    test_names = [
        "ABC Construction LLC",
        "Smith & Jones Roofing",
        "XYZ Corp.",
        "A-1 Plumbing Co",
        "Total Quality Services Inc"
    ]
    
    for name in test_names:
        variations = generate_name_variations(name)
        print(f"Original: '{name}'")
        print(f"Variations:")
        for i, var in enumerate(variations, 1):
            print(f"  {i}. '{var}'")
        print()

def demo_evidence_collection():
    """Demonstrate evidence collection process."""
    
    print("=== Evidence Collection Demo ===\n")
    
    from coi_auditor.pdf_classifier import collect_meta_evidence
    
    test_cases = [
        "ABC Construction",
        "TOTAL", 
        "123",
        "N/A",
        "   ",
        "INACTIVE"
    ]
    
    print("Meta evidence collection for various names:\n")
    
    for name in test_cases:
        evidence = collect_meta_evidence({'name': name})
        print(f"Name: '{name}'")
        print(f"  Administrative: {evidence['is_administrative']}")
        print(f"  Confidence Boost: {evidence['confidence_boost']}")
        if evidence['administrative_markers']:
            print(f"  Markers: {', '.join(evidence['administrative_markers'])}")
        print()

if __name__ == '__main__':
    try:
        demo_classification()
        demo_name_variations()
        demo_evidence_collection()
        
        print("=== Demo Complete ===")
        print("\nThe PDF classifier is ready for integration with the main audit system.")
        print("Key features demonstrated:")
        print("- Four-state classification (VERIFIED, UNVERIFIED, TECHNICAL_FAILURE, ADMINISTRATIVE)")
        print("- Evidence-based confidence scoring")
        print("- Administrative entry detection")
        print("- Name variation generation for fuzzy matching")
        print("- Comprehensive diagnostic output")
        print("- Action and report destination determination")
        
    except Exception as e:
        print(f"Demo failed with error: {e}")
        import traceback
        traceback.print_exc()