"""
Comprehensive PDF Status Classification System

This module implements an evidence-based PDF classification system that distinguishes
between technical failures and legitimate business cases, replacing the simple 
"Missing PDF" classification with a four-state model.

States:
- VERIFIED: PDF exists and was successfully processed
- UNVERIFIED: No PDF found (business issue - certificate not provided)
- TECHNICAL_FAILURE: PDF exists but couldn't be processed (technical issue)
- ADMINISTRATIVE: Non-business entries (TOTALS, headers, etc.)
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional, Union
from datetime import date
import re

# Import existing constants and functions
from .constants import STATUS_OK, STATUS_GAP, STATUS_MISSING_PDF, STATUS_MISSING_DATES, STATUS_PDF_ERROR
from coi_auditor.pdf_parser import find_coi_pdfs, extract_dates_from_pdf

logger = logging.getLogger(__name__)

# New classification states
class PDFState:
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED" 
    TECHNICAL_FAILURE = "TECHNICAL_FAILURE"
    ADMINISTRATIVE = "ADMINISTRATIVE"
    UNKNOWN = "UNKNOWN"

# Action types
class ActionType:
    NONE = "None"
    REVIEW_EXTRACTION = "Review extraction quality"
    FIX_TECHNICAL = "Fix technical issue"
    INVESTIGATE_ROOT_CAUSE = "Investigate root cause"
    REQUEST_CERTIFICATE = "Request certificate"
    MANUAL_INVESTIGATION = "Manual investigation"
    SKIP = "Skip"
    MANUAL_REVIEW = "Manual review"

# Report destinations
class ReportDestination:
    SUCCESS_LOG = "Success Log"
    QA_REPORT = "QA Report"
    ERRORS_REPORT = "errors_report"
    GAPS_REPORT = "gaps_report"
    METADATA_REPORT = "metadata_report"
    REVIEW_QUEUE = "review_queue"
    DIAGNOSTICS = "diagnostics"

def classify_pdf_status(subcontractor: Dict[str, Any], pdf_directory: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Classify PDF status using evidence-based framework.
    
    Args:
        subcontractor: Dict with subcontractor data including 'name'
        pdf_directory: Path to directory containing PDF files
        config: Configuration object
    
    Returns:
        dict: {
            'state': 'VERIFIED' | 'UNVERIFIED' | 'TECHNICAL_FAILURE' | 'ADMINISTRATIVE',
            'confidence': float (0.0 to 1.0),
            'evidence': dict,
            'action': str,
            'report_destination': str
        }
    """
    sub_name = subcontractor.get('name', '')
    
    logger.debug(f"Classifying PDF status for subcontractor: {sub_name}")
    
    # Collect all evidence
    evidence = collect_all_evidence(subcontractor, pdf_directory, config)
    
    # Calculate confidence based on evidence
    confidence = calculate_confidence(evidence)
    
    # Determine state based on evidence
    state = determine_state(evidence, confidence)
    
    # Determine action and report destination
    action, report_destination = determine_action_and_destination(state, confidence)
    
    result = {
        'state': state,
        'confidence': confidence,
        'evidence': evidence,
        'action': action,
        'report_destination': report_destination
    }
    
    logger.debug(f"Classification result for {sub_name}: {state} (confidence: {confidence:.2f})")
    
    return result

def collect_all_evidence(subcontractor: Dict[str, Any], pdf_directory: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Collect all types of evidence for classification.
    
    Evidence Types:
    1. Direct Evidence
       - PDF exists with exact name match
       - PDF was successfully processed
       - Dates were extracted

    2. Circumstantial Evidence  
       - Files with similar names exist (with similarity scores)
       - Directory contains patterns matching subcontractor
       - Historical data shows previous PDFs
       - Other subcontractors from same company have PDFs

    3. Negative Evidence
       - No files found after exhaustive search
       - All similar files belong to other subcontractors
       - Subcontractor marked as "inactive" or "terminated"

    4. Meta Evidence
       - Row contains non-business data (TOTALS, headers)
       - Subcontractor name has administrative markers
       - Excel row has specific status flags
    """
    sub_name = subcontractor.get('name', '')
    
    evidence = {
        'direct': {},
        'circumstantial': {},
        'negative': {},
        'meta': {},
        'search_paths': [],
        'similar_files': [],
        'processing_errors': []
    }
    
    # Collect meta evidence first (administrative entries)
    evidence['meta'] = collect_meta_evidence(subcontractor)
    
    # If it's administrative, we can return early
    if evidence['meta'].get('is_administrative', False):
        return evidence
    
    # Collect direct evidence
    evidence['direct'] = collect_direct_evidence(subcontractor, pdf_directory, config)
    
    # Collect circumstantial evidence
    evidence['circumstantial'] = collect_circumstantial_evidence(subcontractor, pdf_directory, config)
    
    # Collect negative evidence
    evidence['negative'] = collect_negative_evidence(subcontractor, pdf_directory, config, evidence)
    
    return evidence

def collect_meta_evidence(subcontractor: Dict[str, Any]) -> Dict[str, Any]:
    """
    Collect meta evidence about whether this is an administrative entry.
    """
    sub_name = subcontractor.get('name', '').strip()
    
    meta_evidence = {
        'is_administrative': False,
        'administrative_markers': [],
        'confidence_boost': 0.0
    }
    
    # Check for administrative markers
    administrative_patterns = [
        r'^total[s]?$',
        r'^sub[\s-]?total[s]?$',
        r'^grand[\s-]?total[s]?$',
        r'^header$',
        r'^footer$',
        r'^summary$',
        r'^\s*$',  # Empty or whitespace only
        r'^n/?a$',
        r'^tbd$',
        r'^pending$',
        r'^inactive$',
        r'^terminated$',
        r'^cancelled$',
        r'^void$'
    ]
    
    for pattern in administrative_patterns:
        if re.match(pattern, sub_name, re.IGNORECASE):
            meta_evidence['is_administrative'] = True
            meta_evidence['administrative_markers'].append(f"Name matches pattern: {pattern}")
            meta_evidence['confidence_boost'] = 1.0
            break
    
    # Check for numeric-only names (often row numbers or IDs)
    if sub_name.isdigit():
        meta_evidence['is_administrative'] = True
        meta_evidence['administrative_markers'].append("Name is numeric only")
        meta_evidence['confidence_boost'] = 0.9
    
    # Check for very short names (likely incomplete data)
    if len(sub_name) <= 2 and not sub_name.isdigit():
        meta_evidence['is_administrative'] = True
        meta_evidence['administrative_markers'].append("Name is too short")
        meta_evidence['confidence_boost'] = 0.8
    
    return meta_evidence

def collect_direct_evidence(subcontractor: Dict[str, Any], pdf_directory: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Collect direct evidence about PDF existence and processing.
    """
    sub_name = subcontractor.get('name', '')
    
    direct_evidence = {
        'pdf_exists': False,
        'pdf_processed': False,
        'dates_extracted': False,
        'found_pdfs': [],
        'processing_results': [],
        'extraction_errors': []
    }
    
    try:
        # Use existing PDF finding logic
        fuzzy_config = config.get('fuzzy_matching', {})
        found_pdfs = find_coi_pdfs(pdf_directory, sub_name, fuzzy_config=fuzzy_config)
        
        direct_evidence['found_pdfs'] = found_pdfs
        direct_evidence['pdf_exists'] = len(found_pdfs) > 0
        
        if found_pdfs:
            # Try to process each found PDF
            for pdf_path_str, indicator in found_pdfs:
                pdf_path = Path(pdf_path_str)
                
                try:
                    # Attempt to extract dates
                    extraction_result = extract_dates_from_pdf(pdf_path, indicator=indicator)
                    dates_dict, notes = extraction_result
                    
                    processing_result = {
                        'pdf_path': pdf_path_str,
                        'processed': True,
                        'dates_found': bool(dates_dict and any(dates_dict.values())),
                        'dates': dates_dict,
                        'notes': notes
                    }
                    
                    direct_evidence['processing_results'].append(processing_result)
                    
                    if processing_result['processed']:
                        direct_evidence['pdf_processed'] = True
                    
                    if processing_result['dates_found']:
                        direct_evidence['dates_extracted'] = True
                        
                except Exception as e:
                    error_msg = f"Error processing {pdf_path_str}: {str(e)}"
                    direct_evidence['extraction_errors'].append(error_msg)
                    logger.debug(error_msg)
                    
                    processing_result = {
                        'pdf_path': pdf_path_str,
                        'processed': False,
                        'dates_found': False,
                        'error': str(e)
                    }
                    direct_evidence['processing_results'].append(processing_result)
    
    except Exception as e:
        error_msg = f"Error in direct evidence collection for {sub_name}: {str(e)}"
        direct_evidence['extraction_errors'].append(error_msg)
        logger.debug(error_msg)
    
    return direct_evidence

def collect_circumstantial_evidence(subcontractor: Dict[str, Any], pdf_directory: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Collect circumstantial evidence about potential PDF matches.
    """
    sub_name = subcontractor.get('name', '')
    
    circumstantial_evidence = {
        'similar_files': [],
        'name_variations': [],
        'directory_patterns': [],
        'company_matches': []
    }
    
    try:
        # Get all PDF files in directory for similarity analysis
        pdf_files = []
        if os.path.isdir(pdf_directory):
            for item in os.listdir(pdf_directory):
                if item.lower().endswith('.pdf'):
                    pdf_files.append(item)
        
        # Generate name variations to search for
        name_variations = generate_name_variations(sub_name)
        circumstantial_evidence['name_variations'] = name_variations
        
        # Find similar files using fuzzy matching
        similar_files = find_similar_files(sub_name, pdf_files, name_variations)
        circumstantial_evidence['similar_files'] = similar_files
        
        # Look for company/pattern matches
        company_matches = find_company_pattern_matches(sub_name, pdf_files)
        circumstantial_evidence['company_matches'] = company_matches
        
    except Exception as e:
        logger.debug(f"Error in circumstantial evidence collection for {sub_name}: {str(e)}")
    
    return circumstantial_evidence

def collect_negative_evidence(subcontractor: Dict[str, Any], pdf_directory: str, config: Dict[str, Any], existing_evidence: Dict[str, Any]) -> Dict[str, Any]:
    """
    Collect negative evidence about why no PDF was found.
    """
    sub_name = subcontractor.get('name', '')
    
    negative_evidence = {
        'exhaustive_search_completed': False,
        'directory_accessible': False,
        'no_similar_files': False,
        'search_thoroughness': 0.0
    }
    
    try:
        # Check if directory is accessible
        negative_evidence['directory_accessible'] = os.path.isdir(pdf_directory) and os.access(pdf_directory, os.R_OK)
        
        # If we have no direct evidence and no circumstantial evidence
        direct_ev = existing_evidence.get('direct', {})
        circumstantial_ev = existing_evidence.get('circumstantial', {})
        
        has_direct = direct_ev.get('pdf_exists', False)
        has_circumstantial = len(circumstantial_ev.get('similar_files', [])) > 0
        
        if not has_direct and not has_circumstantial:
            negative_evidence['no_similar_files'] = True
            negative_evidence['exhaustive_search_completed'] = True
            negative_evidence['search_thoroughness'] = 0.8  # High thoroughness if we found nothing
        
    except Exception as e:
        logger.debug(f"Error in negative evidence collection for {sub_name}: {str(e)}")
    
    return negative_evidence

def generate_name_variations(name: str) -> List[str]:
    """
    Generate variations of a subcontractor name for fuzzy matching.
    """
    variations = [name]
    
    # Remove common business suffixes
    business_suffixes = ['LLC', 'Inc', 'Corp', 'Co', 'Ltd', 'LP', 'LLP', 'PC']
    name_clean = name
    for suffix in business_suffixes:
        name_clean = re.sub(rf'\b{suffix}\.?\b', '', name_clean, flags=re.IGNORECASE).strip()
    
    if name_clean != name:
        variations.append(name_clean)
    
    # Add variations with different punctuation
    variations.append(re.sub(r'[^\w\s]', '', name))  # Remove all punctuation
    variations.append(re.sub(r'[^\w\s]', ' ', name))  # Replace punctuation with spaces
    variations.append(name.replace('&', 'and'))
    variations.append(name.replace(' and ', ' & '))
    
    # Remove duplicates while preserving order
    seen = set()
    unique_variations = []
    for var in variations:
        var_clean = var.strip()
        if var_clean and var_clean not in seen:
            seen.add(var_clean)
            unique_variations.append(var_clean)
    
    return unique_variations

def find_similar_files(target_name: str, pdf_files: List[str], name_variations: List[str]) -> List[Dict[str, Any]]:
    """
    Find files similar to the target name using fuzzy matching.
    """
    similar_files = []
    
    try:
        # Import fuzzy matching if available
        from rapidfuzz import fuzz
        
        for pdf_file in pdf_files:
            # Remove .pdf extension for comparison
            file_name_base = pdf_file[:-4] if pdf_file.lower().endswith('.pdf') else pdf_file
            
            best_score = 0.0
            best_variation = target_name
            
            # Check against all name variations
            for variation in name_variations:
                score = fuzz.token_sort_ratio(variation.lower(), file_name_base.lower())
                if score > best_score:
                    best_score = score
                    best_variation = variation
            
            # Only include files with reasonable similarity
            if best_score >= 60:  # Configurable threshold
                similar_files.append({
                    'filename': pdf_file,
                    'similarity_score': best_score,
                    'matched_variation': best_variation,
                    'file_name_base': file_name_base
                })
        
        # Sort by similarity score (highest first)
        similar_files.sort(key=lambda x: x['similarity_score'], reverse=True)
        
    except ImportError:
        logger.debug("rapidfuzz not available for similarity matching")
    except Exception as e:
        logger.debug(f"Error in similarity matching: {str(e)}")
    
    return similar_files

def find_company_pattern_matches(target_name: str, pdf_files: List[str]) -> List[Dict[str, Any]]:
    """
    Find files that might belong to the same company or follow similar patterns.
    """
    company_matches = []
    
    try:
        # Extract potential company name (first few words)
        words = target_name.split()
        if len(words) >= 2:
            company_part = ' '.join(words[:2])  # First two words
            
            for pdf_file in pdf_files:
                file_name_base = pdf_file[:-4] if pdf_file.lower().endswith('.pdf') else pdf_file
                
                # Check if company part appears in filename
                if company_part.lower() in file_name_base.lower():
                    company_matches.append({
                        'filename': pdf_file,
                        'company_part': company_part,
                        'match_type': 'company_name'
                    })
    
    except Exception as e:
        logger.debug(f"Error in company pattern matching: {str(e)}")
    
    return company_matches

def calculate_confidence(evidence: Dict[str, Any]) -> float:
    """
    Calculate confidence score based on evidence quality.
    
    Weights:
    - Direct evidence: 0.5 each (PDF exists, processed)
    - Circumstantial: 0.1-0.3 based on strength
    - Negative evidence: 0.2-0.3 based on thoroughness
    - Meta evidence: Override to 1.0 for administrative
    """
    confidence = 0.0
    
    # Meta evidence can override everything
    meta_ev = evidence.get('meta', {})
    if meta_ev.get('is_administrative', False):
        return meta_ev.get('confidence_boost', 1.0)
    
    # Direct evidence (highest weight)
    direct_ev = evidence.get('direct', {})
    pdf_exists = direct_ev.get('pdf_exists', False)
    pdf_processed = direct_ev.get('pdf_processed', False)
    dates_extracted = direct_ev.get('dates_extracted', False)
    
    if pdf_exists:
        confidence += 0.5  # Higher weight for PDF existence
    if pdf_processed:
        confidence += 0.3
    if dates_extracted:
        confidence += 0.2
    
    # Special case: If PDF exists but has processing errors, we're confident it's a technical failure
    processing_errors = direct_ev.get('extraction_errors', [])
    if pdf_exists and processing_errors:
        confidence = max(confidence, 0.8)  # High confidence for clear technical failures
    
    # If we have strong direct evidence, we're confident
    if confidence >= 0.7:
        return min(confidence, 1.0)
    
    # Circumstantial evidence
    circumstantial_ev = evidence.get('circumstantial', {})
    similar_files = circumstantial_ev.get('similar_files', [])
    
    if similar_files:
        # Weight by best similarity score
        best_score = max(f['similarity_score'] for f in similar_files) / 100.0
        confidence += best_score * 0.3
    
    # Negative evidence (increases confidence in UNVERIFIED state)
    negative_ev = evidence.get('negative', {})
    if negative_ev.get('exhaustive_search_completed', False):
        confidence += 0.4  # Higher weight for thorough search
    if negative_ev.get('no_similar_files', False):
        confidence += 0.3  # Higher weight for no matches
    
    return min(confidence, 1.0)

def determine_state(evidence: Dict[str, Any], confidence: float) -> str:
    """
    Determine state based on evidence and confidence.
    
    Logic:
    - If PDF processed successfully → VERIFIED
    - If administrative entry → ADMINISTRATIVE
    - If PDF exists but not processed → TECHNICAL_FAILURE
    - If strong circumstantial match exists → TECHNICAL_FAILURE (likely matching problem)
    - If exhaustive search completed with no matches → UNVERIFIED
    """
    # Check for administrative first
    meta_ev = evidence.get('meta', {})
    if meta_ev.get('is_administrative', False):
        return PDFState.ADMINISTRATIVE
    
    # Check direct evidence
    direct_ev = evidence.get('direct', {})
    
    # If PDF was successfully processed with dates
    if direct_ev.get('pdf_processed', False) and direct_ev.get('dates_extracted', False):
        return PDFState.VERIFIED
    
    # If PDF exists but couldn't be processed or no dates extracted
    if direct_ev.get('pdf_exists', False):
        return PDFState.TECHNICAL_FAILURE
    
    # Check circumstantial evidence for potential technical issues
    circumstantial_ev = evidence.get('circumstantial', {})
    similar_files = circumstantial_ev.get('similar_files', [])
    
    # If we have high-confidence similar files, it's likely a matching/technical issue
    if similar_files:
        best_score = max(f['similarity_score'] for f in similar_files)
        if best_score >= 80:  # High similarity suggests technical matching issue
            return PDFState.TECHNICAL_FAILURE
    
    # Check negative evidence
    negative_ev = evidence.get('negative', {})
    
    # If we did an exhaustive search and found nothing, or have good negative evidence
    if (negative_ev.get('exhaustive_search_completed', False) or
        negative_ev.get('no_similar_files', False) or
        confidence >= 0.5):  # Lower threshold for UNVERIFIED
        return PDFState.UNVERIFIED
    
    # Default to unknown if we can't determine confidently
    return PDFState.UNKNOWN

def determine_action_and_destination(state: str, confidence: float) -> Tuple[str, str]:
    """
    Determine action and report destination based on state and confidence.
    
    Action Determination Matrix:
    | State | Confidence | Action | Report Destination |
    |-------|------------|--------|-------------------|
    | VERIFIED | High | None | Success Log |
    | VERIFIED | Low | Review extraction quality | QA Report |
    | TECHNICAL_FAILURE | High | Fix technical issue | errors_report |
    | TECHNICAL_FAILURE | Low | Investigate root cause | errors_report + diagnostics |
    | UNVERIFIED | High | Request certificate | gaps_report |
    | UNVERIFIED | Low | Manual investigation | gaps_report + review_queue |
    | ADMINISTRATIVE | Any | Skip | metadata_report |
    | UNKNOWN | Any | Manual review | review_queue |
    """
    
    if state == PDFState.VERIFIED:
        if confidence >= 0.8:
            return ActionType.NONE, ReportDestination.SUCCESS_LOG
        else:
            return ActionType.REVIEW_EXTRACTION, ReportDestination.QA_REPORT
    
    elif state == PDFState.TECHNICAL_FAILURE:
        if confidence >= 0.7:
            return ActionType.FIX_TECHNICAL, ReportDestination.ERRORS_REPORT
        else:
            return ActionType.INVESTIGATE_ROOT_CAUSE, f"{ReportDestination.ERRORS_REPORT} + {ReportDestination.DIAGNOSTICS}"
    
    elif state == PDFState.UNVERIFIED:
        if confidence >= 0.7:
            return ActionType.REQUEST_CERTIFICATE, ReportDestination.GAPS_REPORT
        else:
            return ActionType.MANUAL_INVESTIGATION, f"{ReportDestination.GAPS_REPORT} + {ReportDestination.REVIEW_QUEUE}"
    
    elif state == PDFState.ADMINISTRATIVE:
        return ActionType.SKIP, ReportDestination.METADATA_REPORT
    
    else:  # UNKNOWN
        return ActionType.MANUAL_REVIEW, ReportDestination.REVIEW_QUEUE

def generate_diagnostic_record(subcontractor: Dict[str, Any], state: str, confidence: float, evidence: Dict[str, Any], action: str) -> Dict[str, Any]:
    """
    Generate comprehensive diagnostic record for non-verified subcontractors.
    
    Include:
    - Evidence summary with search paths and similar files
    - Name variations tried
    - Historical context if available
    - Recommended actions and manual review hints
    """
    sub_name = subcontractor.get('name', '')
    sub_id = subcontractor.get('id', '')
    
    diagnostic = {
        'subcontractor_name': sub_name,
        'subcontractor_id': sub_id,
        'classification_state': state,
        'confidence_score': confidence,
        'recommended_action': action,
        'evidence_summary': {},
        'search_details': {},
        'manual_review_hints': [],
        'timestamp': str(date.today())
    }
    
    # Evidence summary
    direct_ev = evidence.get('direct', {})
    circumstantial_ev = evidence.get('circumstantial', {})
    negative_ev = evidence.get('negative', {})
    meta_ev = evidence.get('meta', {})
    
    diagnostic['evidence_summary'] = {
        'pdf_found': direct_ev.get('pdf_exists', False),
        'pdf_processed': direct_ev.get('pdf_processed', False),
        'dates_extracted': direct_ev.get('dates_extracted', False),
        'similar_files_count': len(circumstantial_ev.get('similar_files', [])),
        'is_administrative': meta_ev.get('is_administrative', False),
        'exhaustive_search': negative_ev.get('exhaustive_search_completed', False)
    }
    
    # Search details
    diagnostic['search_details'] = {
        'name_variations_tried': circumstantial_ev.get('name_variations', []),
        'similar_files': circumstantial_ev.get('similar_files', []),
        'company_matches': circumstantial_ev.get('company_matches', []),
        'processing_errors': direct_ev.get('extraction_errors', [])
    }
    
    # Generate manual review hints
    hints = []
    
    if state == PDFState.TECHNICAL_FAILURE:
        if direct_ev.get('pdf_exists', False):
            hints.append("PDF file exists but processing failed - check file corruption or format issues")
        if circumstantial_ev.get('similar_files'):
            best_match = max(circumstantial_ev['similar_files'], key=lambda x: x['similarity_score'])
            hints.append(f"Consider if '{best_match['filename']}' (similarity: {best_match['similarity_score']}%) is the correct file")
    
    elif state == PDFState.UNVERIFIED:
        hints.append("No PDF found after exhaustive search - likely missing certificate")
        if circumstantial_ev.get('name_variations'):
            hints.append(f"Searched for variations: {', '.join(circumstantial_ev['name_variations'][:3])}")
    
    elif state == PDFState.ADMINISTRATIVE:
        hints.append("Entry appears to be administrative/non-business - can be safely skipped")
        if meta_ev.get('administrative_markers'):
            hints.append(f"Administrative markers: {', '.join(meta_ev['administrative_markers'])}")
    
    elif state == PDFState.UNKNOWN:
        hints.append("Classification uncertain - requires manual investigation")
        if confidence < 0.5:
            hints.append("Low confidence in classification - review evidence carefully")
    
    diagnostic['manual_review_hints'] = hints
    
    return diagnostic

def get_legacy_status_mapping(state: str) -> str:
    """
    Map new classification states to legacy status constants for backward compatibility.
    """
    mapping = {
        PDFState.VERIFIED: STATUS_OK,
        PDFState.UNVERIFIED: STATUS_MISSING_PDF,
        PDFState.TECHNICAL_FAILURE: STATUS_PDF_ERROR,
        PDFState.ADMINISTRATIVE: "ADMINISTRATIVE",  # New status
        PDFState.UNKNOWN: STATUS_MISSING_PDF  # Default to missing for safety
    }
    
    return mapping.get(state, STATUS_MISSING_PDF)

# Utility functions for integration
def is_administrative_entry(subcontractor_name: str) -> bool:
    """
    Quick check if a subcontractor name represents an administrative entry.
    """
    evidence = collect_meta_evidence({'name': subcontractor_name})
    return evidence.get('is_administrative', False)

def get_classification_summary(classification_result: Dict[str, Any]) -> str:
    """
    Generate a human-readable summary of the classification result.
    """
    state = classification_result['state']
    confidence = classification_result['confidence']
    action = classification_result['action']
    
    return f"{state} (confidence: {confidence:.1%}) - {action}"