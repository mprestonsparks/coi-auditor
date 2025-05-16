"""Main entry point for the COI Auditor application."""

import logging
import sys
import time
import argparse
from pathlib import Path
import tempfile
import platform # Added for OS detection
import shutil # For cleanup, though TemporaryDirectory handles it.
import openpyxl # For reading error reports

from .config import load_config
from .excel_handler import read_subcontractors, update_excel, write_gaps_report, run_excel_sanity_checks
# We will need a new function from excel_handler, e.g., create_error_report_workbook_for_validation
# For now, let's assume it will be imported or defined when excel_handler is modified.
# from .excel_handler import create_error_report_workbook_for_validation
from .audit import process_subcontractor
from .verify import workbook_is_clean


# Configure logging
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s')
log_handler = logging.StreamHandler(sys.stdout) # Log to console
log_handler.setFormatter(log_formatter)

logger = logging.getLogger('coi_auditor') # Get root logger for the package
logger.addHandler(log_handler)
logger.setLevel(logging.DEBUG) # Set desired logging level (e.g., INFO, DEBUG)

# Add file logging
import os
# Ensure logs directory exists
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logs_dir = os.path.join(project_root, 'logs')
os.makedirs(logs_dir, exist_ok=True)
log_file_path = os.path.join(logs_dir, 'coi_audit.log')
file_log_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
file_log_handler.setFormatter(log_formatter)
logger.addHandler(file_log_handler)

# Headers for the ERROR_REPORT sheet in validation mode
VALIDATION_ERROR_REPORT_HEADERS = ["Subcontractor Name", "Subcontractor ID", "Issue Type", "Details", "Policy Type", "Effective Date", "Expiration Date", "File Path", "Page Number"]


def perform_single_pdf_audit(pdf_path: Path, output_excel_path: Path, config: dict):
    """
    Processes a single PDF, generates an audit report (specifically an ERROR_REPORT sheet),
    and saves it to the specified Excel path.
    This uses a hypothetical excel_handler.create_error_report_workbook_for_validation.
    """
    logger.info(f"Auditing PDF for validation: {pdf_path}")
    
    # Create a dummy subcontractor entry for process_subcontractor
    # 'row' is usually from the main Excel, here it's nominal.
    # 'coi_pdf_path' is crucial.
    # Other fields like 'expected_insured_name' etc., would normally come from the main Excel.
    # For validation, process_subcontractor will run based on the PDF content and general rules.
    # If these rules require specific 'expected' values not present, it might generate 'gaps'.
    dummy_sub = {
        'name': pdf_path.stem,
        'id': f"fixture_{pdf_path.stem}", # Synthetic ID
        'coi_pdf_path': str(pdf_path),
        'row': 1, # Nominal row number
        # Add other keys that process_subcontractor might expect, with default/None values
        # if they are not relevant for a standalone PDF audit or should be derived by the process.
        'expected_insured_name': None,
        'gl_policy_num_expected': None,
        'wc_policy_num_expected': None,
        # ... any other fields process_subcontractor might access from the 'sub' dict
    }

    try:
        # process_subcontractor is expected to use the new date extraction logic internally.
        # Pass the fixture's pdf_path as direct_pdf_path
        sub_result, sub_gaps = process_subcontractor(dummy_sub, config, direct_pdf_path=pdf_path)
        
        # We need to import or have access to the function that writes the error report.
        # This function will be created in excel_handler.py
        from .excel_handler import create_error_report_workbook_for_validation
        
        # The sub_gaps from process_subcontractor will form the content of the ERROR_REPORT.
        # The headers should match what workbook_is_clean expects or what is meaningful for an error report.
        # Based on typical gap structure:
        # gap = {
        #     'subcontractor_name': sub_name,
        #     'subcontractor_id': sub_id,
        #     'policy_type': policy_type_str,
        #     'issue_type': "Date Gap", # or "Coverage Gap", "Missing Policy", "Unreadable Date"
        #     'details': f"Coverage gap: {last_exp_date.strftime('%Y-%m-%d')} to {current_eff_date.strftime('%Y-%m-%d')}",
        #     'effective_date': current_eff_date.strftime('%Y-%m-%d') if current_eff_date else "N/A",
        #     'expiration_date': current_exp_date.strftime('%Y-%m-%d') if current_exp_date else "N/A",
        #     'file_path': str(pdf_file_path),
        #     'page_number': page_num
        # }
        # So, VALIDATION_ERROR_REPORT_HEADERS should align with these keys.
        create_error_report_workbook_for_validation(output_excel_path, sub_gaps, VALIDATION_ERROR_REPORT_HEADERS)
        logger.info(f"Temporary audit report for {pdf_path} saved to {output_excel_path}")

    except Exception as e:
        logger.error(f"Failed during single PDF audit for {pdf_path}: {e}", exc_info=True)
        # Create an error report indicating this failure
        error_gap = [{
            'Subcontractor Name': pdf_path.stem,
            'Subcontractor ID': f"fixture_{pdf_path.stem}",
            'Issue Type': "Audit Processing Error",
            'Details': f"Critical error during audit: {e}",
            'Policy Type': "N/A",
            'Effective Date': "N/A",
            'Expiration Date': "N/A",
            'File Path': str(pdf_path),
            'Page Number': "N/A"
        }]
        # Ensure the import is available
        from .excel_handler import create_error_report_workbook_for_validation
        create_error_report_workbook_for_validation(output_excel_path, error_gap, VALIDATION_ERROR_REPORT_HEADERS)
        logger.info(f"Error audit report for {pdf_path} saved to {output_excel_path}")


def run_batch_validation(fixtures_dir_str: str):
    """
    Runs the audit process for all PDFs in a fixtures directory and verifies
    that their "ERROR_REPORT" sheets are clean.
    """
    logger.info(f"Starting batch validation for fixtures in: {fixtures_dir_str}")
    config = load_config() # Needed for process_subcontractor via perform_single_pdf_audit

    fixtures_path = Path(fixtures_dir_str)
    if not fixtures_path.is_dir():
        logger.error(f"Fixtures directory not found: {fixtures_path}")
        print(f"Error: Fixtures directory '{fixtures_path}' does not exist.")
        sys.exit(1)

    all_pdf_files = sorted(list(fixtures_path.glob('*.pdf'))) # Sort for consistent order

    target_debug_pdf = "31-W Insulation_2023-11-06.pdf" # Temporary for debugging
    pdf_files_to_process = []

    if not all_pdf_files:
        logger.warning(f"No PDF files found in fixtures directory: {fixtures_path}")
        print(f"No PDF files found in '{fixtures_path}'. Batch validation finished.")
        sys.exit(0) # Success, as there's nothing to fail on.

    for pdf_path in all_pdf_files:
        if pdf_path.name == target_debug_pdf:
            pdf_files_to_process.append(pdf_path)
            logger.info(f"Target debug PDF '{target_debug_pdf}' found. Will process only this file.")
            break # Found our target
    
    if not pdf_files_to_process:
        logger.error(f"Target debug PDF '{target_debug_pdf}' not found in {fixtures_dir_str}. Searched {len(all_pdf_files)} files.")
        # print(f"Error: Target debug PDF '{target_debug_pdf}' not found in '{fixtures_dir_str}'.")
        # sys.exit(1) # Exiting might be too abrupt if this function is called elsewhere.
        # For now, let's return False or an empty list of failures, or let it proceed and fail naturally.
        # Given the context of batch validation, exiting or clearly indicating failure is appropriate.
        # The original code exits if no PDFs are found, so exiting here is consistent.
        print(f"Error: Target debug PDF '{target_debug_pdf}' not found in '{fixtures_dir_str}'. Cannot proceed with focused validation.")
        sys.exit(1) # Or return False if this function is part of a larger flow that can handle it.

    logger.info(f"Processing 1 target PDF file: {target_debug_pdf}")

    overall_success = True
    failed_reports_details = [] # Stores (pdf_file_name, list_of_error_rows_as_strings)

    cleanup_args = {}
    if platform.system() == "Windows":
        logger.info("Windows OS detected, setting ignore_cleanup_errors=True for TemporaryDirectory.")
        cleanup_args['ignore_cleanup_errors'] = True

    with tempfile.TemporaryDirectory(prefix="coi_val_", **cleanup_args) as tmpdir:
        tmpdir_path = Path(tmpdir)
        logger.info(f"Using temporary directory for reports: {tmpdir_path}")

        for pdf_file in pdf_files_to_process:
            logger.info(f"--- Processing fixture: {pdf_file.name} ---")
            temp_excel_name = f"{pdf_file.stem}_audit_report.xlsx"
            temp_excel_path = tmpdir_path / temp_excel_name
            
            pdf_had_processing_error = False
            try:
                perform_single_pdf_audit(pdf_file, temp_excel_path, config)
                
                if not temp_excel_path.exists():
                    logger.error(f"Audit report was not created for {pdf_file.name} at {temp_excel_path}")
                    overall_success = False
                    failed_reports_details.append((pdf_file.name, [f"| Critical Error | Report file not created"]))
                    continue

                if not workbook_is_clean(temp_excel_path):
                    overall_success = False
                    logger.warning(f"Validation FAILED for {pdf_file.name}. Report: {temp_excel_path}")
                    # Extract errors for reporting
                    current_pdf_errors = []
                    try:
                        wb = openpyxl.load_workbook(temp_excel_path, read_only=True, data_only=True)
                        if "ERROR_REPORT" in wb.sheetnames:
                            error_sheet = wb["ERROR_REPORT"]
                            # Check if sheet has more than just a header
                            has_errors = False
                            for row_idx, row_values in enumerate(error_sheet.iter_rows(min_row=2, values_only=True)):
                                if any(cell is not None for cell in row_values):
                                    has_errors = True
                                    error_details = " | ".join(str(cell).strip() if cell is not None else "" for cell in row_values)
                                    current_pdf_errors.append(error_details)
                            if not has_errors and error_sheet.max_row > 1 : # Header exists but no data rows with content
                                logger.info(f"ERROR_REPORT for {pdf_file.name} has rows but they appear empty after header.")
                            elif not has_errors: # No error rows found despite workbook_is_clean returning False (should be rare)
                                logger.warning(f"workbook_is_clean was False for {pdf_file.name}, but no error rows extracted from ERROR_REPORT.")
                                current_pdf_errors.append("| Internal Discrepancy | workbook_is_clean reported errors, but none found in sheet.")


                        else: # ERROR_REPORT sheet missing, but workbook_is_clean was False
                            logger.error(f"ERROR_REPORT sheet missing in {temp_excel_path}, but workbook_is_clean indicated errors.")
                            current_pdf_errors.append("| Critical Error | ERROR_REPORT sheet missing, inconsistent with clean check")
                        
                        if not current_pdf_errors: # If still no errors, but it was not clean
                             current_pdf_errors.append("| Unknown Error | Workbook deemed not clean, but no specific errors extracted.")
                        failed_reports_details.append((pdf_file.name, current_pdf_errors))

                    except Exception as e_read:
                        logger.error(f"Error reading error details from {temp_excel_path} for {pdf_file.name}: {e_read}")
                        failed_reports_details.append((pdf_file.name, [f"| Read Error | Could not parse report: {e_read}"]))
                else:
                    logger.info(f"Validation PASSED for {pdf_file.name}.")
                    # temp_excel_path.unlink() # Optionally delete clean reports

            except Exception as e_process:
                logger.error(f"Critical error processing {pdf_file.name} during validation: {e_process}", exc_info=True)
                overall_success = False
                # Attempt to log this as a failure for the PDF
                failed_reports_details.append((pdf_file.name, [f"| Processing Crash | Audit function failed: {e_process}"]))
                pdf_had_processing_error = True # Ensure this PDF is marked as failed.
                # If perform_single_pdf_audit created an error report due to its own exception handling,
                # workbook_is_clean might pick it up. If not, this ensures failure.

    if overall_success:
        logger.info("All PDF fixtures processed successfully and are clean.")
        print("\nSUCCESS: Batch validation complete. All COI fixtures are clean.")
        sys.exit(0)
    else:
        logger.error("Batch validation FAILED. Errors found in one or more COIs.")
        print("\nFAILURE: Batch validation encountered errors. Details below:")
        for pdf_name, error_list in failed_reports_details:
            if error_list:
                for error_detail_str in error_list:
                    print(f"{pdf_name} | {error_detail_str}")
            else:
                # This case should ideally be covered by specific error messages above
                print(f"{pdf_name} | An unspecified error occurred or error report was problematic.")
        
        print("\nFailure summary: One or more COIs had errors reported or failed processing.")
        sys.exit(1)


def run_audit():
    """Executes the full COI audit process based on the main Excel file."""
    start_time = time.time()
    logger.info("Starting COI Audit Process...")

    # 1. Load Configuration
    logger.info("Loading configuration from .env file...")
    config = load_config()
    logger.debug(f"Configuration loaded: {config}")

    # 2. Run sanity checks before anything else
    logger.info("Running Excel sanity checks...")
    run_excel_sanity_checks(config['excel_file_path'])

    try:
        # 3. Read Subcontractor List
        logger.info(f"Reading subcontractors from Excel: {config['excel_file_path']}")
        subcontractors, headers = read_subcontractors(config['excel_file_path'])
        if not subcontractors:
            logger.warning("No subcontractors found in the Excel file. Exiting.")
            return

        # 3. Process Each Subcontractor
        all_results = []
        all_gaps = []
        total_subs = len(subcontractors)
        logger.info(f"Processing {total_subs} subcontractors...")

        for i, sub in enumerate(subcontractors):
            logger.info(f"Processing {i+1}/{total_subs}: {sub.get('name', 'N/A')}")
            try:
                sub_result, sub_gaps = process_subcontractor(sub, config)
                all_results.append(sub_result)
                all_gaps.extend(sub_gaps)
            except Exception as sub_e:
                logger.error(f"Failed to process subcontractor {sub.get('name', 'N/A')} (Row: {sub.get('row', 'N/A')}): {sub_e}", exc_info=True)
                # Add a basic error result for this sub to update Excel
                all_results.append({
                    'row': sub.get('row'),
                    'name': sub.get('name', 'N/A'),
                    'id': sub.get('id', 'N/A'),
                    'notes': f"ERROR PROCESSING: {sub_e}",
                    'gl_gap_status': 'Error',
                    'wc_gap_status': 'Error'
                })
                # Also add to gaps report
                all_gaps.append({
                     'subcontractor_name': sub.get('name', 'N/A'),
                     'subcontractor_id': sub.get('id', 'N/A'),
                     'issue_type': 'Processing Error',
                     'details': str(sub_e)
                })

        logger.info("Finished processing all subcontractors.")

        # 4. Update Excel File
        logger.info(f"Updating Excel file: {config['excel_file_path']}")
        update_excel(config['excel_file_path'], all_results, headers)

        # 5. Write Gaps Report (CSV and Excel worksheet)
        logger.info(f"Writing gaps report to: {config['output_directory_path']} and GAPS_REPORT worksheet in Excel")
        write_gaps_report(config['output_directory_path'], all_gaps, excel_path=config['excel_file_path'])

        end_time = time.time()
        logger.info(f"COI Audit Process Completed Successfully in {end_time - start_time:.2f} seconds.")

    except FileNotFoundError as fnf_e:
        logger.error(f"File Not Found Error: {fnf_e}. Please check paths in .env file.")
    except ValueError as val_e:
        logger.error(f"Configuration or Data Error: {val_e}. Please check .env file or input Excel file.", exc_info=True)
        _write_fatal_error(val_e)
    except PermissionError as perm_e:
         logger.error(f"Permission Error: {perm_e}. Ensure files are not open and permissions are correct.", exc_info=True)
         _write_fatal_error(perm_e)
    except ImportError as imp_e:
         logger.error(f"Import Error: {imp_e}. Ensure all dependencies are installed (pip install -r requirements.txt). Run as 'python -m coi_auditor.main'", exc_info=True)
         _write_fatal_error(imp_e)
    except Exception as e:
        logger.error(f"An unexpected error occurred during the audit process: {e}", exc_info=True)
        _write_fatal_error(e)

def _write_fatal_error(exc):
    import traceback
    err_path = os.path.join(logs_dir, 'fatal_error.txt')
    try:
        with open(err_path, 'w', encoding='utf-8') as f:
            f.write('FATAL ERROR DURING AUDIT\n')
            f.write(traceback.format_exc())
    except Exception as file_exc:
        print(f"Could not write fatal error file: {file_exc}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="COI Auditor: Process COI PDFs and validate.")
    parser.add_argument(
        "--validate-batch",
        metavar="FIXTURES_DIRECTORY",
        type=str,
        help="Run validation harness on all PDFs in the specified directory."
    )
    # Add other arguments if the original script had them or if run_audit needs them.
    # For now, if no args, it runs the standard audit.

    args = parser.parse_args()

    # If --validate-batch is used, set an environment variable.
    # This allows config.py to adjust its requirements before load_config() is called.
    if args.validate_batch:
        import os # os is imported globally (line 31), but being explicit for this critical step.
        os.environ['COI_VALIDATION_MODE'] = '1'
        # Logger is set up globally (lines 21-39), so it should be available here.
        logger.info("COI_VALIDATION_MODE environment variable set due to --validate-batch flag.")

    # Ensure the logs directory exists (moved from global scope to main execution path)
    # This was previously at the top level, good to ensure it's contextually created.
    project_root_for_logs = Path(__file__).resolve().parent.parent.parent
    logs_dir_for_main = project_root_for_logs / 'logs'
    os.makedirs(logs_dir_for_main, exist_ok=True)
    # Note: logger setup (handlers) is still global. This just ensures dir exists when main runs.


    if args.validate_batch:
        # User must also create the tests/fixtures directory manually.
        # We can add a check here for convenience.
        fixtures_target_path = Path("tests/fixtures/")
        if not fixtures_target_path.exists():
            logger.warning(f"Recommended fixtures directory '{fixtures_target_path}' does not exist. Please create it and add test PDFs.")
        elif not any(fixtures_target_path.glob('*.pdf')) and Path(args.validate_batch) == fixtures_target_path:
             logger.warning(f"Fixtures directory '{fixtures_target_path}' is empty. Add PDFs for validation.")

        run_batch_validation(args.validate_batch)
    else:
        # Default action: run the standard audit process
        run_audit()

