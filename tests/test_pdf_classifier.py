"""
Tests for the PDF classifier module.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.coi_auditor.pdf_classifier import (
    classify_pdf_status,
    collect_meta_evidence,
    generate_name_variations,
    PDFState,
    ActionType,
    ReportDestination,
    is_administrative_entry,
    get_classification_summary
)

class TestPDFClassifier:
    
    def test_administrative_detection(self):
        """Test detection of administrative entries."""
        # Test various administrative patterns
        admin_names = [
            "TOTAL",
            "Sub-Total", 
            "GRAND TOTAL",
            "Header",
            "   ",  # Whitespace only
            "N/A",
            "TBD",
            "123",  # Numeric only
            "INACTIVE",
            "TERMINATED"
        ]
        
        for name in admin_names:
            assert is_administrative_entry(name), f"Should detect '{name}' as administrative"
            
            evidence = collect_meta_evidence({'name': name})
            assert evidence['is_administrative'], f"Meta evidence should mark '{name}' as administrative"
    
    def test_business_name_not_administrative(self):
        """Test that legitimate business names are not marked as administrative."""
        business_names = [
            "ABC Construction LLC",
            "Smith & Sons Roofing",
            "Total Quality Services",  # Contains "total" but not exact match
            "123 Main Street Contractors",  # Contains numbers but not only numbers
            "A-1 Plumbing"
        ]
        
        for name in business_names:
            assert not is_administrative_entry(name), f"Should NOT detect '{name}' as administrative"
    
    def test_name_variations_generation(self):
        """Test generation of name variations for fuzzy matching."""
        test_name = "ABC Construction LLC"
        variations = generate_name_variations(test_name)
        
        # Should include original name
        assert test_name in variations
        
        # Should include version without LLC
        assert "ABC Construction" in variations
        
        # Should include version without punctuation
        assert "ABC Construction LLC" in variations
        
        # Should not have duplicates
        assert len(variations) == len(set(variations))
    
    def test_ampersand_variations(self):
        """Test name variations handle ampersands correctly."""
        test_name = "Smith & Jones"
        variations = generate_name_variations(test_name)
        
        assert "Smith and Jones" in variations
        
        test_name2 = "Smith and Jones"
        variations2 = generate_name_variations(test_name2)
        
        assert "Smith & Jones" in variations2
    
    @patch('src.coi_auditor.pdf_classifier.find_coi_pdfs')
    @patch('src.coi_auditor.pdf_classifier.extract_dates_from_pdf')
    def test_verified_classification(self, mock_extract, mock_find):
        """Test classification of successfully processed PDFs."""
        # Mock successful PDF finding and processing
        mock_find.return_value = [('/path/to/test.pdf', 'indicator')]
        mock_extract.return_value = (
            {'gl_eff_date': '2024-01-01', 'gl_exp_date': '2024-12-31'},
            ['Successfully extracted dates']
        )
        
        subcontractor = {'name': 'Test Company', 'id': '123'}
        config = {'fuzzy_matching': {}}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            result = classify_pdf_status(subcontractor, temp_dir, config)
            
            assert result['state'] == PDFState.VERIFIED
            assert result['confidence'] > 0.8
            assert result['action'] == ActionType.NONE
            assert result['report_destination'] == ReportDestination.SUCCESS_LOG
    
    @patch('src.coi_auditor.pdf_classifier.find_coi_pdfs')
    def test_unverified_classification(self, mock_find):
        """Test classification when no PDF is found."""
        # Mock no PDFs found
        mock_find.return_value = []
        
        subcontractor = {'name': 'Missing Company', 'id': '456'}
        config = {'fuzzy_matching': {}}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            result = classify_pdf_status(subcontractor, temp_dir, config)
            
            assert result['state'] == PDFState.UNVERIFIED
            assert result['action'] == ActionType.REQUEST_CERTIFICATE
            assert ReportDestination.GAPS_REPORT in result['report_destination']
    
    @patch('src.coi_auditor.pdf_classifier.find_coi_pdfs')
    @patch('src.coi_auditor.pdf_classifier.extract_dates_from_pdf')
    def test_technical_failure_classification(self, mock_extract, mock_find):
        """Test classification when PDF exists but processing fails."""
        # Mock PDF found but processing fails
        mock_find.return_value = [('/path/to/test.pdf', 'indicator')]
        mock_extract.side_effect = Exception("PDF processing error")
        
        subcontractor = {'name': 'Error Company', 'id': '789'}
        config = {'fuzzy_matching': {}}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            result = classify_pdf_status(subcontractor, temp_dir, config)
            
            assert result['state'] == PDFState.TECHNICAL_FAILURE
            assert result['action'] == ActionType.FIX_TECHNICAL
            assert ReportDestination.ERRORS_REPORT in result['report_destination']
    
    def test_administrative_classification(self):
        """Test classification of administrative entries."""
        subcontractor = {'name': 'TOTAL', 'id': '999'}
        config = {'fuzzy_matching': {}}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            result = classify_pdf_status(subcontractor, temp_dir, config)
            
            assert result['state'] == PDFState.ADMINISTRATIVE
            assert result['confidence'] == 1.0
            assert result['action'] == ActionType.SKIP
            assert result['report_destination'] == ReportDestination.METADATA_REPORT
    
    def test_classification_summary(self):
        """Test generation of human-readable classification summary."""
        result = {
            'state': PDFState.VERIFIED,
            'confidence': 0.95,
            'action': ActionType.NONE
        }
        
        summary = get_classification_summary(result)
        assert "VERIFIED" in summary
        assert "95.0%" in summary
        assert ActionType.NONE in summary
    
    @patch('src.coi_auditor.pdf_classifier.os.listdir')
    @patch('src.coi_auditor.pdf_classifier.os.path.isdir')
    def test_similar_files_detection(self, mock_isdir, mock_listdir):
        """Test detection of similar files for circumstantial evidence."""
        mock_isdir.return_value = True
        mock_listdir.return_value = [
            'ABC_Construction_2024.pdf',
            'XYZ_Roofing_2024.pdf', 
            'ABC_Const_2023.pdf'
        ]
        
        # This test requires rapidfuzz, so we'll mock it if not available
        try:
            from rapidfuzz import fuzz
            
            subcontractor = {'name': 'ABC Construction', 'id': '123'}
            config = {'fuzzy_matching': {}}
            
            with tempfile.TemporaryDirectory() as temp_dir:
                result = classify_pdf_status(subcontractor, temp_dir, config)
                
                # Should find similar files in circumstantial evidence
                similar_files = result['evidence']['circumstantial']['similar_files']
                assert len(similar_files) > 0
                
                # Should have high similarity scores for ABC files
                abc_files = [f for f in similar_files if 'ABC' in f['filename']]
                assert len(abc_files) > 0
                
        except ImportError:
            pytest.skip("rapidfuzz not available for similarity testing")

if __name__ == '__main__':
    pytest.main([__file__])