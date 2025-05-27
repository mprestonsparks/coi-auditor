"""Core logic for processing subcontractors, aggregating dates, and detecting gaps."""

from coi_auditor.pdf_parser import find_coi_pdfs, extract_dates_from_pdf # Ensure extract_dates_from_pdf is correctly imported
import logging
import os
from datetime import date
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List

# Gap status constants
STATUS_OK = "OK"
STATUS_GAP = "Gap"
STATUS_MISSING_PDF = "Missing PDF"
STATUS_MISSING_DATES = "Dates Not Found"
STATUS_PDF_ERROR = "PDF Error"

logger = logging.getLogger(__name__) # Will inherit Rich handler from main.py

def aggregate_dates(all_dates_results: List[Tuple[str, Tuple[Dict[str, Optional[date]], List[str]]]]) -> Tuple[Dict[str, Optional[date]], List[str]]:
    """Aggregates dates across multiple COI parse results for a single subcontractor.
    
    Args:
        all_dates_results (list): A list of tuples, where each tuple contains:
                                 (pdf_path (str), extracted_data_tuple (Tuple[Dict[str, Optional[date]], List[str]]))
                                 The inner tuple is (dates_dict, notes_list_from_pdf_parser)
                                 
    Returns:
        dict: Aggregated dates {'gl_from': date|None, 'gl_to': date|None,
                                'wc_from': date|None, 'wc_to': date|None}
        list: Combined notes from all processed PDFs for this subcontractor.
    """
    all_gl_effective: List[date] = []
    all_gl_expiration: List[date] = []
    all_wc_effective: List[date] = []
    all_wc_expiration: List[date] = []
    notes: List[str] = []

    valid_pdf_processed = False
    # Each item in all_dates_results is (pdf_path, (dates_dict, notes_list_from_parser))
    for pdf_path, extraction_result in all_dates_results:
        dates_dict, notes_list_from_parser = extraction_result
        if dates_dict: # Check if dates_dict is not None
            gl_eff = dates_dict.get('gl_eff_date')
            gl_exp = dates_dict.get('gl_exp_date')
            wc_eff = dates_dict.get('wc_eff_date')
            wc_exp = dates_dict.get('wc_exp_date')

            if gl_eff: all_gl_effective.append(gl_eff)
            if gl_exp: all_gl_expiration.append(gl_exp)
            if wc_eff: all_wc_effective.append(wc_eff)
            if wc_exp: all_wc_expiration.append(wc_exp)
            if gl_eff or gl_exp or wc_eff or wc_exp: # Check if any date was found
                valid_pdf_processed = True # Mark that at least one PDF yielded potential dates
        
        # Combine notes from the parser
        if notes_list_from_parser:
            # Robustly join notes, converting any non-string items to strings
            joined_parser_notes = " / ".join(str(n) for n in notes_list_from_parser)
            notes.append(f"[cyan]{os.path.basename(pdf_path)}[/cyan]: {joined_parser_notes}")
        elif not dates_dict: # If dates_dict itself was None (e.g. critical PDF error)
            notes.append(f"[cyan]{os.path.basename(pdf_path)}[/cyan]: [bold red]Critical PDF processing error prevented date extraction.[/bold red]")


    aggregated = {
        'gl_from': min(all_gl_effective) if all_gl_effective else None,
        'gl_to': max(all_gl_expiration) if all_gl_expiration else None,
        'wc_from': min(all_wc_effective) if all_wc_effective else None,
        'wc_to': max(all_wc_expiration) if all_wc_expiration else None,
    }
    
    # If no PDFs were processed successfully, add a specific note
    if not valid_pdf_processed and not notes: # Check if notes list is also empty
        notes.append("[yellow]No valid data extracted from any PDF.[/yellow]")
    elif not valid_pdf_processed and any("Critical PDF processing error" in note for note in notes):
        pass # Error already noted
    elif not valid_pdf_processed: # Some notes exist, but no dates were actually processed
        notes.append("[yellow]No valid dates found in processed PDFs, though PDFs were accessed.[/yellow]")


    return aggregated, notes

def check_coverage_gap(coverage_from: Optional[date], coverage_to: Optional[date], audit_start: date, audit_end: date) -> Tuple[str, str]:
    """Checks for a gap in coverage within the audit period.
    
    Returns:
        str: Gap status (STATUS_OK or STATUS_GAP).
        str: Description of the gap, if any.
    """
    if not coverage_from or not coverage_to:
        # Cannot determine gap if dates are missing
        return STATUS_GAP, "Missing effective or expiration date."
        
    gap_detected = False
    gap_reasons: List[str] = []

    # Check 1: Coverage starts after the audit period begins
    if coverage_from > audit_start:
        gap_detected = True
        gap_reasons.append(f"Starts after audit start ([yellow]{coverage_from}[/yellow] > [green]{audit_start}[/green])")

    # Check 2: Coverage ends before the audit period ends
    if coverage_to < audit_end:
        gap_detected = True
        gap_reasons.append(f"Ends before audit end ([yellow]{coverage_to}[/yellow] < [green]{audit_end}[/green])")
        
    # Check 3: Effective date is after expiration date (invalid data)
    if coverage_from > coverage_to:
         gap_detected = True # Treat invalid range as a gap
         gap_reasons.append(f"Effective date ([yellow]{coverage_from}[/yellow]) is after expiration date ([yellow]{coverage_to}[/yellow])")

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
    
    logger.info(f"--- Processing Subcontractor: [bold cyan]{sub_name}[/bold cyan] (ID: {sub_id}) ---")
    if direct_pdf_path:
        logger.info(f"Using direct PDF path for [cyan]{sub_name}[/cyan]: [green]{direct_pdf_path}[/green]")
    
    # Result structure for this subcontractor
    result: Dict[str, Any] = {
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
    all_pdf_results: List[Tuple[str, Tuple[Dict[str, Optional[date]], List[str]]]] = []


    # 1. Find associated PDFs
    coi_pdfs = find_coi_pdfs(pdf_dir, sub_name, direct_pdf_path=direct_pdf_path)
    
    if not coi_pdfs:
        log_message = f"No COI PDFs found for [cyan]{sub_name}[/cyan]."
        if direct_pdf_path:
            log_message += f" Direct path provided was [yellow]{direct_pdf_path}[/yellow]."
        else:
            log_message += f" Searched in [yellow]{pdf_dir}[/yellow]."
        logger.warning(f"[magenta]{log_message}[/magenta] Flagging as '[bold red]{STATUS_MISSING_PDF}[/bold red]'.")
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

    # 2. Extract dates from each PDF
    pdf_processing_errors = False
    for pdf_path_str, indicator in coi_pdfs: # pdf_path_str is a string path
        pdf_path_obj = Path(pdf_path_str) # Convert to Path object if needed by extract_dates_from_pdf
        logger.debug(f"Parsing PDF: [green]{os.path.basename(pdf_path_str)}[/green] for [cyan]{sub_name}[/cyan] (indicator: {indicator})")
        
        extraction_data_tuple: Tuple[Dict[str, Optional[date]], List[str]] = ({}, []) # Default empty result
        try:
            extraction_data_tuple = extract_dates_from_pdf(pdf_path_obj, indicator=indicator)
        except Exception as e:
            error_note = f"Critical error during PDF processing of [yellow]{os.path.basename(pdf_path_str)}[/yellow]: {e}"
            logger.error(f"[bold red]{error_note}[/bold red]", exc_info=True)
            extraction_data_tuple = ({}, [error_note]) 

        all_pdf_results.append((pdf_path_str, extraction_data_tuple))
        
        notes_from_parser = extraction_data_tuple[1]
        # Robustly join notes, converting any non-string items to strings, using " / " as separator
        current_pdf_note_str = " / ".join(str(item) for item in notes_from_parser) if notes_from_parser else ""
        
        if "error" in current_pdf_note_str.lower() or not extraction_data_tuple[0] and not notes_from_parser: # No dates and no specific notes means likely an issue
            pdf_processing_errors = True
            issue_type = STATUS_PDF_ERROR if "error" in current_pdf_note_str.lower() else STATUS_MISSING_DATES
            log_detail = current_pdf_note_str if current_pdf_note_str else "No dates extracted and no specific error notes from parser."
            logger.error(f"[bold red]{issue_type} from [yellow]{os.path.basename(pdf_path_str)}[/yellow] for [cyan]{sub_name}[/cyan]: {log_detail}[/bold red]")
            gap_report_entries.append({
                "Subcontractor Name": sub_name,
                "Subcontractor ID": sub_id,
                "Issue Type": issue_type,
                "Details": log_detail,
                "Policy Type": "N/A",
                "Effective Date": "N/A",
                "Expiration Date": "N/A",
                "File Path": pdf_path_str,
                "Page Number": "N/A" 
            })

    # 3. Aggregate dates across all found PDFs
    aggregated_dates, combined_notes = aggregate_dates(all_pdf_results)
    result['gl_from'] = aggregated_dates.get('gl_from')
    result['gl_to'] = aggregated_dates.get('gl_to')
    result['wc_from'] = aggregated_dates.get('wc_from')
    result['wc_to'] = aggregated_dates.get('wc_to')
    
    # Prepend existing notes if any, then add new combined notes
    existing_notes = result['notes']
    new_notes_str = "; ".join(combined_notes)
    if existing_notes and new_notes_str:
        result['notes'] = f"{existing_notes}; {new_notes_str}"
    elif new_notes_str:
        result['notes'] = new_notes_str
    # else existing_notes remains as is (or empty if it was empty)


    # Add note if processing errors occurred and not already captured
    if pdf_processing_errors and "PDF Processing Errors Encountered" not in result['notes']:
        result['notes'] = f"PDF Processing Errors Encountered; {result['notes']}" if result['notes'] else "PDF Processing Errors Encountered"

    # 4. Detect Coverage Gaps
    # General Liability
    if result['gl_from'] and result['gl_to']:
        gl_status, gl_gap_details = check_coverage_gap(result['gl_from'], result['gl_to'], audit_start, audit_end)
        result['gl_gap_status'] = gl_status
        if gl_status == STATUS_GAP:
            logger.warning(f"[magenta]GL Gap detected for [cyan]{sub_name}[/cyan]: {gl_gap_details}[/magenta]")
            if result['gl_from'] > audit_start:
                result['gl_gap_ranges'].append((audit_start, result['gl_from']))
            if result['gl_to'] < audit_end:
                result['gl_gap_ranges'].append((result['gl_to'], audit_end))
            contributing_pdf_path_gl = "Multiple or N/A"
            if all_pdf_results:
                for p_path, (actual_dates_dict, _note) in all_pdf_results:
                    if actual_dates_dict and (actual_dates_dict.get('gl_eff_date') or actual_dates_dict.get('gl_exp_date')):
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
    elif any(pdf_res[1] and pdf_res[1][0] and (pdf_res[1][0].get('gl_eff_date') or pdf_res[1][0].get('gl_exp_date')) for pdf_res in all_pdf_results):
         result['gl_gap_status'] = STATUS_MISSING_DATES
         result['notes'] = f"{result['notes']}; GL dates incomplete across PDFs" if result['notes'] else "GL dates incomplete across PDFs"
         logger.warning(f"[magenta]GL dates incomplete for [cyan]{sub_name}[/cyan]. Flagging as '[bold red]{STATUS_MISSING_DATES}[/bold red]'.[/magenta]")
         gap_report_entries.append({
            "Subcontractor Name": sub_name,
            "Subcontractor ID": sub_id,
            "Issue Type": STATUS_MISSING_DATES,
            "Details": 'GL effective or expiration date missing after aggregation from available PDFs.',
            "Policy Type": "GL",
            "Effective Date": result['gl_from'].strftime('%Y-%m-%d') if result['gl_from'] else "N/A",
            "Expiration Date": result['gl_to'].strftime('%Y-%m-%d') if result['gl_to'] else "N/A",
            "File Path": "See notes for individual PDF issues",
            "Page Number": "N/A"
         })
    elif not pdf_processing_errors: 
         result['gl_gap_status'] = STATUS_MISSING_DATES
         result['notes'] = f"{result['notes']}; No GL dates found in PDFs" if result['notes'] else "No GL dates found in PDFs"
         logger.warning(f"[magenta]No GL dates found for [cyan]{sub_name}[/cyan] in any PDF. Flagging as '[bold red]{STATUS_MISSING_DATES}[/bold red]'.[/magenta]")
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
            logger.warning(f"[magenta]WC Gap detected for [cyan]{sub_name}[/cyan]: {wc_gap_details}[/magenta]")
            if result['wc_from'] > audit_start:
                result['wc_gap_ranges'].append((audit_start, result['wc_from']))
            if result['wc_to'] < audit_end:
                result['wc_gap_ranges'].append((result['wc_to'], audit_end))
            contributing_pdf_path_wc = "Multiple or N/A"
            if all_pdf_results:
                for p_path, (actual_dates_dict, _note) in all_pdf_results:
                    if actual_dates_dict and (actual_dates_dict.get('wc_eff_date') or actual_dates_dict.get('wc_expiration')):
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
    elif any(r[1] and r[1][0] and (r[1][0].get('wc_eff_date') or r[1][0].get('wc_expiration')) for r in all_pdf_results):
         result['wc_gap_status'] = STATUS_MISSING_DATES
         result['notes'] = f"{result['notes']}; WC dates incomplete across PDFs" if result['notes'] else "WC dates incomplete across PDFs"
         logger.warning(f"[magenta]WC dates incomplete for [cyan]{sub_name}[/cyan]. Flagging as '[bold red]{STATUS_MISSING_DATES}[/bold red]'.[/magenta]")
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
         result['notes'] = f"{result['notes']}; No WC dates found in PDFs" if result['notes'] else "No WC dates found in PDFs"
         logger.warning(f"[magenta]No WC dates found for [cyan]{sub_name}[/cyan] in any PDF. Flagging as '[bold red]{STATUS_MISSING_DATES}[/bold red]'.[/magenta]")
         gap_report_entries.append({ # Add entry for missing WC dates if no PDF errors
            "Subcontractor Name": sub_name,
            "Subcontractor ID": sub_id,
            "Issue Type": STATUS_MISSING_DATES,
            "Details": 'No WC dates found in any successfully parsed PDFs.',
            "Policy Type": "WC",
            "Effective Date": "N/A",
            "Expiration Date": "N/A",
            "File Path": "N/A (No relevant PDFs or dates found)",
            "Page Number": "N/A"
         })


    return result, gap_report_entries

if __name__ == '__main__':
    # Example usage/test (requires config and other modules)
    print("Audit module - run main.py for full execution.")
    # Configure basic logging for testing this module directly
    # Use DEBUG level to see detailed logs from pdf_parser and this module during testing
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
    
    # Load configuration
    from coi_auditor.config import load_config # Assuming config.py is in the same package
    app_config = load_config()

    # Create a dummy subcontractor dictionary
    test_subcontractor = {
        'name': 'Fernando Hernandez', # Match a name in your test fixtures
        'id': 'FH-001',
        'row': 2 # Example row number
    }
    
    # Robust path to a sample PDF in tests/fixtures
    # Path(__file__) gives the path to the current file (audit.py)
    # .resolve() makes it an absolute path
    # .parent gives the directory of the current file (src/coi_auditor/)
    # .parent.parent gives the project root (assuming src/coi_auditor/audit.py structure)
    script_dir = Path(__file__).resolve().parent
    project_root_for_test = script_dir.parent.parent
    sample_pdf_path_fixture = project_root_for_test / "tests" / "fixtures" / "FernandoHernandez_2024-09-19.pdf"

    if not sample_pdf_path_fixture.exists():
        logging.error(f"Test PDF not found at: {sample_pdf_path_fixture}. Skipping process_subcontractor test.")
    else:
        logging.info(f"Attempting to process subcontractor with PDF: {sample_pdf_path_fixture}")
        # Process the subcontractor using the function from this module
        # No need to import process_subcontractor if it's in the same file
        processed_result, reported_gaps = process_subcontractor(test_subcontractor, app_config, direct_pdf_path=sample_pdf_path_fixture)

        # Print the result
        print("\n--- process_subcontractor Test Result ---")
        print(f"Result: {processed_result}")
        print(f"Gaps Reported: {reported_gaps}")
        print("--------------------------------------")
    
    # Dummy data for basic tests
    test_audit_start = date(2024, 1, 1)
    test_audit_end = date(2024, 12, 31)
    
    print("\n--- Testing Gap Checking ---")
    gap_check_tests = [
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
    
    for eff, exp in gap_check_tests:
        status, details = check_coverage_gap(eff, exp, test_audit_start, test_audit_end)
        print(f"Eff: {eff}, Exp: {exp} => Status: {status}, Details: {details}")
        
    print("\n--- Testing Date Aggregation ---")
    # Note: The structure for test_results for aggregate_dates needs to match
    # List[Tuple[str, Tuple[Dict[str, Optional[date]], List[str]]]]
    aggregation_test_results: List[Tuple[str, Tuple[Dict[str, Optional[date]], List[str]]]] = [
        ('doc1.pdf', ({'gl_eff_date': date(2024,1,1), 'gl_exp_date': date(2024,6,30), 'wc_eff_date': date(2024,1,1), 'wc_exp_date': date(2024,12,31)}, ["Note 1"])),
        ('doc2.pdf', ({'gl_eff_date': date(2024,7,1), 'gl_exp_date': date(2024,12,31)}, ["GL only"])), # Missing WC
        ('doc3.pdf', ({'wc_eff_date': date(2023,12,1), 'wc_exp_date': date(2024,11,30)}, ["WC renewal"])), # Missing GL
        ('doc4_error.pdf', ({}, ["PDF Error: Corrupted"])), # Simulate error, dates_dict is empty
        ('doc5_nodates.pdf', ({}, ["Dates not found"])), # Simulate no dates found, dates_dict is empty
    ]
    agg_dates, agg_notes = aggregate_dates(aggregation_test_results)
    print(f"Aggregated Dates: {agg_dates}")
    print(f"Aggregated Notes: {agg_notes}")
