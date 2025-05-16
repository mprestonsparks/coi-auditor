"""Core logic for processing subcontractors, aggregating dates, and detecting gaps."""

from coi_auditor.pdf_parser import find_coi_pdfs, extract_dates_from_pdf
import logging
import os
from datetime import date

def visualize_ocr_pipeline(image_path):
    """Placeholder for visualize_ocr_pipeline function."""
    print("visualize_ocr_pipeline called")
    pass

def preprocess_date_region(image_path):
    """Placeholder for preprocess_date_region function."""
    print("preprocess_date_region called")
    pass

def extract_date_text(image):
    """Placeholder for extract_date_text function."""
    print("extract_date_text called")
    pass

def validate_and_normalize_date(date_text):
    """Placeholder for validate_and_normalize_date function."""
    print("validate_and_normalize_date called")
    pass
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List

# Gap status constants
STATUS_OK = "OK"
STATUS_GAP = "Gap"
STATUS_MISSING_PDF = "Missing PDF"
STATUS_MISSING_DATES = "Dates Not Found"
STATUS_PDF_ERROR = "PDF Error"

def aggregate_dates(all_dates_results):
    """Aggregates dates across multiple COI parse results for a single subcontractor.
    
    Args:
        all_dates_results (list): A list of tuples, where each tuple contains:
                                 (pdf_path, {'gl_effective': date|None, ...}, note_string)
                                 
    Returns:
        dict: Aggregated dates {'gl_from': date|None, 'gl_to': date|None, 
                               'wc_from': date|None, 'wc_to': date|None}
        list: Combined notes from all processed PDFs for this subcontractor.
    """
    all_gl_effective = []
    all_gl_expiration = []
    all_wc_effective = []
    all_wc_expiration = []
    notes = []

    valid_pdf_processed = False
    for pdf_path, dates_dict, note in all_dates_results:
        if dates_dict: # Check if dates_dict is not None (might be None on severe error)
            if dates_dict.get('gl_effective'): all_gl_effective.append(dates_dict['gl_effective'])
            if dates_dict.get('gl_expiration'): all_gl_expiration.append(dates_dict['gl_expiration'])
            if dates_dict.get('wc_effective'): all_wc_effective.append(dates_dict['wc_effective'])
            if dates_dict.get('wc_expiration'): all_wc_expiration.append(dates_dict['wc_expiration'])
            valid_pdf_processed = True # Mark that at least one PDF yielded potential dates
        if note: # Collect notes from all attempts
            notes.append(f"{os.path.basename(pdf_path)}: {note}")

    aggregated = {
        'gl_from': min(all_gl_effective) if all_gl_effective else None,
        'gl_to': max(all_gl_expiration) if all_gl_expiration else None,
        'wc_from': min(all_wc_effective) if all_wc_effective else None,
        'wc_to': max(all_wc_expiration) if all_wc_expiration else None,
    }
    
    # If no PDFs were processed successfully, add a specific note
    if not valid_pdf_processed and not notes:
        notes.append("No valid data extracted from any PDF.")

    return aggregated, notes

def check_coverage_gap(coverage_from, coverage_to, audit_start, audit_end):
    """Checks for a gap in coverage within the audit period.
    
    Returns:
        str: Gap status (STATUS_OK or STATUS_GAP).
        str: Description of the gap, if any.
    """
    if not coverage_from or not coverage_to:
        # Cannot determine gap if dates are missing
        return STATUS_GAP, "Missing effective or expiration date."
        
    gap_detected = False
    gap_reasons = []

    # Check 1: Coverage starts after the audit period begins
    if coverage_from > audit_start:
        gap_detected = True
        gap_reasons.append(f"Starts after audit start ({coverage_from} > {audit_start})")

    # Check 2: Coverage ends before the audit period ends
    if coverage_to < audit_end:
        gap_detected = True
        gap_reasons.append(f"Ends before audit end ({coverage_to} < {audit_end})")
        
    # Check 3: Effective date is after expiration date (invalid data)
    if coverage_from > coverage_to:
         gap_detected = True # Treat invalid range as a gap
         gap_reasons.append(f"Effective date ({coverage_from}) is after expiration date ({coverage_to})")

    if gap_detected:
        return STATUS_GAP, "; ".join(gap_reasons)
    else:
        # Check if the entire audit period is covered
        # This condition (coverage_from <= audit_start and coverage_to >= audit_end) is implied if no gaps above were found
        return STATUS_OK, "Coverage spans audit period."


def process_subcontractor(subcontractor: Dict[str, Any], config: Dict[str, Any], direct_pdf_path: Optional[Path] = None) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Processes a single subcontractor: finds PDFs, extracts dates, aggregates, checks gaps.
    If direct_pdf_path is provided, it's used directly for PDF lookup.
    """
    sub_name = subcontractor['name']
    sub_id = subcontractor['id']
    pdf_dir = config['pdf_directory_path']
    audit_start = config['audit_start_date']
    audit_end = config['audit_end_date']
    
    logging.info(f"--- Processing Subcontractor: {sub_name} (ID: {sub_id}) ---")
    if direct_pdf_path:
        logging.info(f"Using direct PDF path for {sub_name}: {direct_pdf_path}")
    
    # Result structure for this subcontractor
    result = {
        'row': subcontractor['row'],
        'name': sub_name,
        'id': sub_id,
        'gl_from': None, 'gl_to': None,
        'wc_from': None, 'wc_to': None,
        'gl_gap_status': '', 'wc_gap_status': '',
        'notes': '',
        'gl_gap_ranges': [],
        'wc_gap_ranges': [],
    }
    gap_report_entries: List[Dict[str, Any]] = [] # List to hold detailed gap info for CSV
    all_pdf_results: List[Tuple[str, Optional[Dict[str, Optional[date]]], str]] = [] # Store results from each PDF

    # 1. Find associated PDFs
    coi_pdfs = find_coi_pdfs(pdf_dir, sub_name, direct_pdf_path=direct_pdf_path)
    
    if not coi_pdfs:
        log_message = f"No COI PDFs found for {sub_name}."
        if direct_pdf_path:
            log_message += f" Direct path provided was {direct_pdf_path}."
        else:
            log_message += f" Searched in {pdf_dir}."
        logging.warning(f"{log_message} Flagging as '{STATUS_MISSING_PDF}'.")
        result['notes'] = STATUS_MISSING_PDF
        result['gl_gap_status'] = STATUS_MISSING_PDF
        result['wc_gap_status'] = STATUS_MISSING_PDF
        gap_report_entries.append({
            "Subcontractor Name": sub_name,
            "Subcontractor ID": sub_id,
            "Issue Type": STATUS_MISSING_PDF,
            "Details": f"No PDF found in directory: {pdf_dir}",
            "Policy Type": "N/A",
            "Effective Date": "N/A",
            "Expiration Date": "N/A",
            "File Path": "N/A", # No specific PDF path
            "Page Number": "N/A"
        })
        return result, gap_report_entries
    else:
        return result, gap_report_entries

    # 2. Extract dates from each PDF
    pdf_processing_errors = False
    for pdf_path, indicator in coi_pdfs:
        logging.debug(f"Parsing PDF: {os.path.basename(pdf_path)} for {sub_name} (indicator: {indicator})")
        extracted_dates, note = {}, ""
        try:
            # 1. Preprocess the date region
            preprocessed_image = preprocess_date_region(pdf_path)

            # 2. Extract date text
            date_text = extract_date_text(preprocessed_image)

            # 3. Validate and normalize date
            validated_date = validate_and_normalize_date(date_text)

            extracted_dates = validated_date

        except Exception as e:
            note = f"Date extraction failed: {e}"
            logging.error(f"Date extraction failed for {os.path.basename(pdf_path)}: {e}")

        all_pdf_results.append((pdf_path, extracted_dates, note))
        if "Error" in note:
            pdf_processing_errors = True
            logging.error(f"Error processing {os.path.basename(pdf_path)} for {sub_name}: {note}")
            gap_report_entries.append({
                "Subcontractor Name": sub_name,
                "Subcontractor ID": sub_id,
                "Issue Type": STATUS_PDF_ERROR,
                "Details": note, # note already contains pdf name if relevant
                "Policy Type": "N/A",
                "Effective Date": "N/A",
                "Expiration Date": "N/A",
                "File Path": str(pdf_path),
                "Page Number": "N/A" # Assuming page number not available from extract_dates_from_pdf
            })

    # 3. Aggregate dates across all found PDFs
    aggregated_dates, combined_notes = aggregate_dates(all_pdf_results)
    result['gl_from'] = aggregated_dates.get('gl_from')
    result['gl_to'] = aggregated_dates.get('gl_to')
    result['wc_from'] = aggregated_dates.get('wc_from')
    result['wc_to'] = aggregated_dates.get('wc_to')
    result['notes'] = "; ".join(combined_notes)

    # Add note if processing errors occurred
    if pdf_processing_errors:
        result['notes'] = f"PDF Processing Errors Encountered; {result['notes']}"

    # 4. Detect Coverage Gaps
    # General Liability
    if result['gl_from'] and result['gl_to']:
        gl_status, gl_gap_details = check_coverage_gap(result['gl_from'], result['gl_to'], audit_start, audit_end)
        result['gl_gap_status'] = gl_status
        if gl_status == STATUS_GAP:
            logging.warning(f"GL Gap detected for {sub_name}: {gl_gap_details}")
            # Compute gap ranges for summary sheet
            # If coverage starts after audit window, add gap before
            if result['gl_from'] > audit_start:
                result['gl_gap_ranges'].append((audit_start, result['gl_from']))
            # If coverage ends before audit window, add gap after
            if result['gl_to'] < audit_end:
                result['gl_gap_ranges'].append((result['gl_to'], audit_end))
            # Find the PDF that contributed to these dates if possible, otherwise use a general note.
            # This is a simplification; a more robust solution might trace which PDF provided the specific dates.
            contributing_pdf_path_gl = "Multiple or N/A"
            if all_pdf_results:
                # Attempt to find a PDF that has GL dates. This is a heuristic.
                for p_path, dates_dict, _ in all_pdf_results:
                    if dates_dict and (dates_dict.get('gl_effective') or dates_dict.get('gl_expiration')):
                        contributing_pdf_path_gl = str(p_path)
                        break
            
            gap_report_entries.append({
                "Subcontractor Name": sub_name,
                "Subcontractor ID": sub_id,
                "Issue Type": STATUS_GAP,
                "Details": gl_gap_details,
                "Policy Type": "GL",
                "Effective Date": result['gl_from'].strftime('%Y-%m-%d') if result['gl_from'] else "N/A",
                "Expiration Date": result['gl_to'].strftime('%Y-%m-%d') if result['gl_to'] else "N/A",
                "File Path": contributing_pdf_path_gl,
                "Page Number": "N/A"
            })
    elif any(r[1] and (r[1].get('gl_effective') or r[1].get('gl_expiration')) for r in all_pdf_results):
         # Dates were found in *some* PDF, but couldn't aggregate a full range (e.g., only eff or only exp overall)
         result['gl_gap_status'] = STATUS_MISSING_DATES
         result['notes'] += "; GL dates incomplete across PDFs" if result['notes'] else "GL dates incomplete across PDFs"
         logging.warning(f"GL dates incomplete for {sub_name}. Flagging as '{STATUS_MISSING_DATES}'.")
         gap_report_entries.append({
            "Subcontractor Name": sub_name,
            "Subcontractor ID": sub_id,
            "Issue Type": STATUS_MISSING_DATES,
            "Details": 'GL effective or expiration date missing after aggregation from available PDFs.',
            "Policy Type": "GL",
            "Effective Date": result['gl_from'].strftime('%Y-%m-%d') if result['gl_from'] else "N/A", # Report what was found
            "Expiration Date": result['gl_to'].strftime('%Y-%m-%d') if result['gl_to'] else "N/A",   # Report what was found
            "File Path": "See notes for individual PDF issues", # General, as it's an aggregation issue
            "Page Number": "N/A"
         })
    elif not pdf_processing_errors: # Only flag as missing if no PDF errors prevented finding them
         # No GL dates found in *any* successfully processed PDF
         result['gl_gap_status'] = STATUS_MISSING_DATES
         result['notes'] += "; No GL dates found in PDFs" if result['notes'] else "No GL dates found in PDFs"
         logging.warning(f"No GL dates found for {sub_name} in any PDF. Flagging as '{STATUS_MISSING_DATES}'.")
         gap_report_entries.append({
            "Subcontractor Name": sub_name,
            "Subcontractor ID": sub_id,
            "Issue Type": STATUS_MISSING_DATES,
            "Details": 'No GL dates found in any successfully parsed PDFs.',
            "Policy Type": "GL",
            "Effective Date": "N/A",
            "Expiration Date": "N/A",
            "File Path": "N/A (No relevant PDFs or dates found)",
            "Page Number": "N/A"
         })

    # Workers' Compensation
    if result['wc_from'] and result['wc_to']:
        wc_status, wc_gap_details = check_coverage_gap(result['wc_from'], result['wc_to'], audit_start, audit_end)
        result['wc_gap_status'] = wc_status
        if wc_status == STATUS_GAP:
            logging.warning(f"WC Gap detected for {sub_name}: {wc_gap_details}")
            # Compute gap ranges for summary sheet
            if result['wc_from'] > audit_start:
                result['wc_gap_ranges'].append((audit_start, result['wc_from']))
            if result['wc_to'] < audit_end:
                result['wc_gap_ranges'].append((result['wc_to'], audit_end))
            contributing_pdf_path_wc = "Multiple or N/A"
            if all_pdf_results:
                for p_path, dates_dict, _ in all_pdf_results:
                    if dates_dict and (dates_dict.get('wc_effective') or dates_dict.get('wc_expiration')):
                        contributing_pdf_path_wc = str(p_path)
                        break

            gap_report_entries.append({
                "Subcontractor Name": sub_name,
                "Subcontractor ID": sub_id,
                "Issue Type": STATUS_GAP,
                "Details": wc_gap_details,
                "Policy Type": "WC",
                "Effective Date": result['wc_from'].strftime('%Y-%m-%d') if result['wc_from'] else "N/A",
                "Expiration Date": result['wc_to'].strftime('%Y-%m-%d') if result['wc_to'] else "N/A",
                "File Path": contributing_pdf_path_wc,
                "Page Number": "N/A"
            })
    elif any(r[1] and (r[1].get('wc_effective') or r[1].get('wc_expiration')) for r in all_pdf_results):
         result['wc_gap_status'] = STATUS_MISSING_DATES
         result['notes'] += "; WC dates incomplete across PDFs" if result['notes'] else "WC dates incomplete across PDFs"
         logging.warning(f"WC dates incomplete for {sub_name}. Flagging as '{STATUS_MISSING_DATES}'.")
         gap_report_entries.append({
            "Subcontractor Name": sub_name,
            "Subcontractor ID": sub_id,
            "Issue Type": STATUS_MISSING_DATES,
            "Details": 'WC effective or expiration date missing after aggregation from available PDFs.',
            "Policy Type": "WC",
            "Effective Date": result['wc_from'].strftime('%Y-%m-%d') if result['wc_from'] else "N/A",
            "Expiration Date": result['wc_to'].strftime('%Y-%m-%d') if result['wc_to'] else "N/A",
            "File Path": "See notes for individual PDF issues",
            "Page Number": "N/A"
         })
    elif not pdf_processing_errors:
         result['wc_gap_status'] = STATUS_MISSING_DATES
         result['notes'] += "; No WC dates found in PDFs" if result['notes'] else "No WC dates found in PDFs"
         logging.warning(f"No WC dates found for {sub_name} in any PDF. Flagging as '{STATUS_MISSING_DATES}'.")



if __name__ == '__main__':
    # Example usage/test (requires config and other modules)
    print("Audit module - run main.py for full execution.")
    logging.basicConfig(level=logging.INFO)
    
    # Load configuration
    from coi_auditor.config import load_config
    config = load_config()

    # Create a dummy subcontractor dictionary
    subcontractor = {
        'name': 'Fernando Hernandez',
        'id': '12345',
        'row': 1
    }

    # Path to the sample PDF
    from pathlib import Path
    pdf_path = Path('test_harness/test_corpus/pdfs/FernandoHernandez_2024-09-19.pdf')

    # Process the subcontractor
    from coi_auditor.audit import process_subcontractor
    result, gaps = process_subcontractor(subcontractor, config, direct_pdf_path=pdf_path)

    # Print the result
    print(f"Result: {result}")
    print(f"Gaps: {gaps}")
    
    # Dummy data for basic tests
    test_audit_start = date(2024, 1, 1)
    test_audit_end = date(2024, 12, 31)
    
    print("\n--- Testing Gap Checking ---")
    tests = [
        (date(2024, 1, 1), date(2024, 12, 31)), # OK
        (date(2023, 12, 1), date(2025, 1, 31)), # OK
        (date(2024, 2, 1), date(2024, 12, 31)), # Gap (starts late)
        (date(2024, 1, 1), date(2024, 11, 30)), # Gap (ends early)
        (date(2024, 3, 1), date(2024, 10, 1)),  # Gap (both)
        (None, date(2024, 12, 31)),            # Gap (missing start)
        (date(2024, 1, 1), None),               # Gap (missing end)
        (date(2025, 1, 1), date(2025, 2, 1)),   # Gap (outside period - starts late)
        (date(2023, 1, 1), date(2023, 12, 1)),   # Gap (outside period - ends early)
        (date(2024, 6, 1), date(2024, 5, 1)),   # Gap (invalid dates)
    ]
    
    for eff, exp in tests:
        status, details = check_coverage_gap(eff, exp, test_audit_start, test_audit_end)
        print(f"Eff: {eff}, Exp: {exp} => Status: {status}, Details: {details}")
        
    print("\n--- Testing Date Aggregation ---")
    test_results = [
        ('doc1.pdf', {'gl_effective': date(2024,1,1), 'gl_expiration': date(2024,6,30), 'wc_effective': date(2024,1,1), 'wc_expiration': date(2024,12,31)}, "Note 1"),
        ('doc2.pdf', {'gl_effective': date(2024,7,1), 'gl_expiration': date(2024,12,31)}, "GL only"), # Missing WC
        ('doc3.pdf', {'wc_effective': date(2023,12,1), 'wc_expiration': date(2024,11,30)}, "WC renewal"), # Missing GL
        ('doc4_error.pdf', None, "PDF Error: Corrupted"), # Simulate error
        ('doc5_nodates.pdf', {}, "Dates not found"), # Simulate no dates found
    ]
    agg_dates, agg_notes = aggregate_dates(test_results)
    print(f"Aggregated Dates: {agg_dates}")
    print(f"Aggregated Notes: {agg_notes}")

