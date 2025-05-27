"""Main entry point for the COI Auditor application."""

import logging
import sys
import time
import argparse
from pathlib import Path
import tempfile
import platform # Added for OS detection
import shutil # For cleanup, though TemporaryDirectory handles it.
import os # Added missing import
import openpyxl # For reading error reports
from tqdm import tqdm
from rich.console import Console
from rich.theme import Theme

# Import setup_logging and load_config from .config
from .config import setup_logging, load_config 
from .excel_handler import (
    read_subcontractors,
    update_excel,
    write_gaps_report,
    run_excel_sanity_checks,
    create_error_report_workbook_for_validation
)
from .audit import process_subcontractor
from .verify import workbook_is_clean
from .pdf_parser import extract_raw_ocr_text_from_pdf, extract_dates_from_pdf # Added for diagnostic and debug modes

# Setup logging as the first step
# Determine project root for default log file path
project_root_for_log_setup = Path(__file__).resolve().parent.parent # src/coi_auditor -> src -> project_root
logs_dir_path_main = project_root_for_log_setup / 'logs'
logs_dir_path_main.mkdir(parents=True, exist_ok=True)
default_log_file = logs_dir_path_main / 'coi_audit_main.log'

# Call setup_logging here. It configures the root logger.
# Subsequent getLogger calls will inherit this configuration.
setup_logging(level="INFO", log_file=str(default_log_file))

# Now, get the logger for this module, which will use the RichHandler.
logger = logging.getLogger(__name__)


# Headers for the ERROR_REPORT sheet in validation mode
VALIDATION_ERROR_REPORT_HEADERS = ["Subcontractor Name", "Subcontractor ID", "Issue Type", "Details", "Policy Type", "Effective Date", "Expiration Date", "File Path", "Page Number"]


def run_diagnostic_pdf_ocr(pdf_path_str: str, config: dict):
    """
    Performs OCR on a single PDF and prints/saves the raw text.
    """
    pdf_path = Path(pdf_path_str)
    if not pdf_path.is_file():
        logger.error(f"[bold red]Diagnostic PDF not found: [yellow]{pdf_path}[/yellow][/bold red]")
        print(f"Error: Diagnostic PDF '{pdf_path}' does not exist.")
        sys.exit(1)

    logger.info(f"Starting diagnostic OCR for PDF: [cyan]{pdf_path}[/cyan]")
    
    raw_text = extract_raw_ocr_text_from_pdf(pdf_path)

    print("\n--- RAW OCR TEXT ---")
    print(raw_text)
    print("--- END RAW OCR TEXT ---\n")

    output_dir_path = Path(config.get('output_directory_path', '.'))
    output_dir_path.mkdir(parents=True, exist_ok=True)
    output_filename = f"diagnostic_ocr_output_{pdf_path.stem}.txt"
    output_file_path = output_dir_path / output_filename
    
    try:
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(f"Diagnostic OCR Output for: {pdf_path.name}\n")
            f.write("="*30 + "\n")
            f.write(raw_text)
        logger.info(f"Diagnostic OCR text saved to: [green]{output_file_path}[/green]")
        print(f"Diagnostic OCR text also saved to: {output_file_path}")
    except IOError as e:
        logger.error(f"[bold red]Failed to save diagnostic OCR text to {output_file_path}: {e}[/bold red]")
        print(f"Error: Could not save diagnostic OCR text to {output_file_path}: {e}")

    logger.info("Diagnostic OCR completed. Exiting.")
    sys.exit(0)


def run_debug_single_pdf(pdf_path_str: str, config: dict):
    """
    Processes a single PDF in debug mode, printing date tokens and table snippets.
    """
    pdf_path = Path(pdf_path_str)
    if not pdf_path.is_file():
        logger.error(f"[bold red]Debug PDF not found: [yellow]{pdf_path}[/yellow][/bold red]")
        print(f"Error: Debug PDF '{pdf_path}' does not exist.")
        sys.exit(1)

    logger.info(f"Starting debug processing for PDF: [cyan]{pdf_path}[/cyan]")
    
    # Set a flag in config or pass a parameter to indicate debug mode
    # For now, we'll rely on a new parameter to extract_dates_from_pdf
    
    # This call will need to be to a modified extract_dates_from_pdf or a wrapper
    # that handles the debug printing.
    # For now, let's assume extract_dates_from_pdf will be modified to accept a debug flag.
    
    print(f"\n--- DEBUG MODE: Processing {pdf_path.name} ---")
    
    # The actual debug prints for tokens and snippets will happen within pdf_parser.py
    # We just invoke the main extraction function here with the debug context.
    # The `extract_dates_from_pdf` function returns (dates_dict, notes_list)
    # We might not need to do much with the results here, as the goal is the printed debug output.
    
    _extracted_dates, _notes = extract_dates_from_pdf(pdf_path, debug_mode=True) # Pass debug_mode=True
    
    # The notes might already contain some of the debug info if we choose to log it there too.
    # For direct console output of tokens/snippets, pdf_parser.py will handle it.

    print(f"--- DEBUG MODE: Finished processing {pdf_path.name} ---")
    logger.info(f"Debug processing for PDF: [cyan]{pdf_path}[/cyan] completed. Exiting.")
    sys.exit(0)


def perform_single_pdf_audit(pdf_path: Path, output_excel_path: Path, config: dict):
    """
    Processes a single PDF, generates an audit report (specifically an ERROR_REPORT sheet),
    and saves it to the specified Excel path.
    """
    logger.info(f"Auditing PDF for validation: [cyan]{pdf_path}[/cyan]")
    
    dummy_sub = {
        'name': pdf_path.stem,
        'id': f"fixture_{pdf_path.stem}", 
        'coi_pdf_path': str(pdf_path),
        'row': 1, 
        'expected_insured_name': None,
        'gl_policy_num_expected': None,
        'wc_policy_num_expected': None,
    }

    try:
        sub_result, sub_gaps = process_subcontractor(dummy_sub, config, direct_pdf_path=pdf_path)
        create_error_report_workbook_for_validation(output_excel_path, sub_gaps, VALIDATION_ERROR_REPORT_HEADERS)
        logger.info(f"Temporary audit report for [cyan]{pdf_path.name}[/cyan] saved to [green]{output_excel_path}[/green]")

    except Exception as e:
        logger.error(f"[bold red]Failed during single PDF audit for [cyan]{pdf_path.name}[/cyan]: {e}[/bold red]", exc_info=True)
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
        create_error_report_workbook_for_validation(output_excel_path, error_gap, VALIDATION_ERROR_REPORT_HEADERS)
        logger.info(f"Error audit report for [cyan]{pdf_path.name}[/cyan] saved to [green]{output_excel_path}[/green]")


def run_batch_validation(fixtures_dir_str: str):
    """
    Runs the audit process for all PDFs in a fixtures directory and verifies
    that their "ERROR_REPORT" sheets are clean.
    """
    logger.info(f"Starting batch validation for fixtures in: [cyan]{fixtures_dir_str}[/cyan]")
    config = load_config() 

    fixtures_path = Path(fixtures_dir_str)
    if not fixtures_path.is_dir():
        logger.error(f"[bold red]Fixtures directory not found: [yellow]{fixtures_path}[/yellow][/bold red]")
        print(f"Error: Fixtures directory '{fixtures_path}' does not exist.")
        sys.exit(1)

    pdf_files_to_process = sorted(list(fixtures_path.glob('*.pdf'))) 

    if not pdf_files_to_process: 
        logger.warning(f"[yellow]No PDF files found in fixtures directory: [cyan]{fixtures_path}[/cyan][/yellow]")
        print(f"No PDF files found in '{fixtures_path}'. Batch validation finished.")
        sys.exit(0) 
    
    logger.info(f"Processing [yellow]{len(pdf_files_to_process)}[/yellow] PDF file(s) from [cyan]{fixtures_path}[/cyan]")

    overall_success = True
    failed_reports_details = [] 

    cleanup_args = {}
    if platform.system() == "Windows":
        logger.info("Windows OS detected, setting ignore_cleanup_errors=True for TemporaryDirectory.")
        cleanup_args['ignore_cleanup_errors'] = True

    with tempfile.TemporaryDirectory(prefix="coi_val_", **cleanup_args) as tmpdir:
        tmpdir_path = Path(tmpdir)
        logger.info(f"Using temporary directory for reports: [cyan]{tmpdir_path}[/cyan]")

        for pdf_file in tqdm(pdf_files_to_process, desc="Validating Fixtures", unit="pdf"):
            logger.info(f"--- Processing fixture: [cyan]{pdf_file.name}[/cyan] ---")
            temp_excel_name = f"{pdf_file.stem}_audit_report.xlsx"
            temp_excel_path = tmpdir_path / temp_excel_name
            
            try:
                perform_single_pdf_audit(pdf_file, temp_excel_path, config)
                
                if not temp_excel_path.exists():
                    logger.error(f"[bold red]Audit report was not created for [yellow]{pdf_file.name}[/yellow] at {temp_excel_path}[/bold red]")
                    overall_success = False
                    failed_reports_details.append((pdf_file.name, [f"| Critical Error | Report file not created"]))
                    continue

                if not workbook_is_clean(temp_excel_path):
                    overall_success = False
                    logger.warning(f"[bold red]Validation FAILED[/bold red] for [yellow]{pdf_file.name}[/yellow]. Report: [green]{temp_excel_path}[/green]")
                    current_pdf_errors = []
                    try:
                        wb = openpyxl.load_workbook(temp_excel_path, read_only=True, data_only=True)
                        if "ERROR_REPORT" in wb.sheetnames:
                            error_sheet = wb["ERROR_REPORT"]
                            has_errors = False
                            for row_idx, row_values in enumerate(error_sheet.iter_rows(min_row=2, values_only=True)):
                                if any(cell is not None for cell in row_values):
                                    has_errors = True
                                    error_details = " | ".join(str(cell).strip() if cell is not None else "" for cell in row_values)
                                    current_pdf_errors.append(error_details)
                            if not has_errors and error_sheet.max_row > 1 : 
                                logger.info(f"ERROR_REPORT for [yellow]{pdf_file.name}[/yellow] has rows but they appear empty after header.")
                            elif not has_errors: 
                                logger.warning(f"[yellow]workbook_is_clean was False for {pdf_file.name}, but no error rows extracted from ERROR_REPORT.[/yellow]")
                                current_pdf_errors.append("| Internal Discrepancy | workbook_is_clean reported errors, but none found in sheet.")
                        else: 
                            logger.error(f"[bold red]ERROR_REPORT sheet missing in {temp_excel_path}, but workbook_is_clean indicated errors.[/bold red]")
                            current_pdf_errors.append("| Critical Error | ERROR_REPORT sheet missing, inconsistent with clean check")
                        
                        if not current_pdf_errors: 
                             current_pdf_errors.append("| Unknown Error | Workbook deemed not clean, but no specific errors extracted.")
                        failed_reports_details.append((pdf_file.name, current_pdf_errors))

                    except Exception as e_read:
                        logger.error(f"[bold red]Error reading error details from {temp_excel_path} for {pdf_file.name}: {e_read}[/bold red]")
                        failed_reports_details.append((pdf_file.name, [f"| Read Error | Could not parse report: {e_read}"]))
                else:
                    logger.info(f"[green]Validation PASSED[/green] for [cyan]{pdf_file.name}[/cyan].")

            except Exception as e_process:
                logger.error(f"[bold red]Critical error processing [yellow]{pdf_file.name}[/yellow] during validation: {e_process}[/bold red]", exc_info=True)
                overall_success = False
                failed_reports_details.append((pdf_file.name, [f"| Processing Crash | Audit function failed: {e_process}"]))

    if overall_success:
        logger.info("[bold green]All PDF fixtures processed successfully and are clean.[/bold green]")
        print("\nSUCCESS: Batch validation complete. All COI fixtures are clean.")
        sys.exit(0)
    else:
        logger.error("[bold red]Batch validation FAILED. Errors found in one or more COIs.[/bold red]")
        print("\n[bold red]FAILURE: Batch validation encountered errors. Details below:[/bold red]")
        for pdf_name, error_list in failed_reports_details:
            if error_list:
                for error_detail_str in error_list:
                    print(f"[yellow]{pdf_name}[/yellow] | {error_detail_str}")
            else:
                print(f"[yellow]{pdf_name}[/yellow] | An unspecified error occurred or error report was problematic.")
        
        print("\n[bold red]Failure summary: One or more COIs had errors reported or failed processing.[/bold red]")
        sys.exit(1)


def run_audit():
    """Executes the full COI audit process based on the main Excel file."""
    start_time = time.time()
    logger.info("[bold green]Starting COI Audit Process...[/bold green]")

    # 1. Load Configuration
    logger.info("Loading configuration...")
    try:
        config = load_config()
        logger.debug(f"Configuration loaded: {config}")
    except ValueError as ve:
        logger.error(f"[bold red]Configuration Error: {ve}[/bold red]", exc_info=True)
        _write_fatal_error(ve)
        sys.exit(1)


    # 2. Run sanity checks before anything else
    logger.info("Running Excel sanity checks...")
    try:
        run_excel_sanity_checks(config['excel_file_path'])
    except Exception as sanity_e:
        logger.error(f"[bold red]Excel sanity check failed: {sanity_e}[/bold red]", exc_info=True)
        _write_fatal_error(sanity_e)
        sys.exit(1)


    try:
        # 3. Read Subcontractor List
        logger.info(f"Reading subcontractors from Excel: [cyan]{config['excel_file_path']}[/cyan]")
        subcontractors, headers = read_subcontractors(config['excel_file_path'])
        if not subcontractors:
            logger.warning("[yellow]No subcontractors found in the Excel file. Exiting.[/yellow]")
            return

        # 3. Process Each Subcontractor
        all_results = []
        all_gaps = []
        total_subs = len(subcontractors)
        logger.info(f"Found [yellow]{total_subs}[/yellow] subcontractors to process.")

        # Progress bar for subcontractor processing
        with tqdm(total=total_subs, desc="[blue]Auditing Subcontractors[/blue]", unit="sub", 
                  bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]",
                  ncols=100, # Adjust width as needed
                  colour='blue' # Set color of the progress bar
                  ) as pbar:
            for sub in subcontractors:
                sub_name = sub.get('name', 'N/A')
                pbar.set_description(f"[blue]Processing[/blue]: [cyan]{sub_name[:30]:<30}[/cyan]") # Truncate and pad name
                logger.info(f"Starting audit for subcontractor: [cyan]{sub_name}[/cyan] (Row: {sub.get('row', 'N/A')})")
                try:
                    sub_result, sub_gaps = process_subcontractor(sub, config)
                    all_results.append(sub_result)
                    all_gaps.extend(sub_gaps)
                    pbar.set_postfix_str("OK", refresh=True)
                except Exception as sub_proc_e: 
                    logger.error(f"[bold red]ERROR[/bold red] processing subcontractor [cyan]{sub.get('name', 'N/A')}[/cyan] (Row: {sub.get('row', 'N/A')}): {sub_proc_e}", exc_info=True)
                    all_results.append({
                        'row': sub.get('row'),
                        'name': sub.get('name', 'N/A'),
                        'id': sub.get('id', 'N/A'),
                        'notes': f"ERROR PROCESSING: {sub_proc_e}",
                        'gl_gap_status': 'Error',
                        'wc_gap_status': 'Error'
                    })
                    all_gaps.append({
                         'subcontractor_name': sub.get('name', 'N/A'),
                         'subcontractor_id': sub.get('id', 'N/A'),
                         'issue_type': 'Processing Error',
                         'details': str(sub_proc_e)
                    })
                    pbar.set_postfix_str("[bold red]ERROR[/bold red]", refresh=True)
                pbar.update(1) 

        logger.info("[green]Finished processing all subcontractors.[/green]")

        # 4. Update Excel File
        logger.info(f"Updating Excel file: [cyan]{config['excel_file_path']}[/cyan]")
        update_excel(config['excel_file_path'], all_results, headers)

        # 5. Write Gaps Report (CSV and Excel worksheet)
        logger.info(f"Writing gaps report to: [cyan]{config['output_directory_path']}[/cyan] and GAPS_REPORT worksheet in Excel")
        write_gaps_report(config['output_directory_path'], all_gaps, excel_path_str=config['excel_file_path'])

        end_time = time.time()
        logger.info(f"[bold green]COI Audit Process Completed Successfully in {end_time - start_time:.2f} seconds.[/bold green]")

    except FileNotFoundError as fnf_e:
        logger.error(f"[bold red]File Not Found Error: {fnf_e}. Please check paths in .env file.[/bold red]")
        _write_fatal_error(fnf_e)
    except ValueError as val_e:
        logger.error(f"[bold red]Configuration or Data Error: {val_e}. Please check .env file or input Excel file.[/bold red]", exc_info=True)
        _write_fatal_error(val_e)
    except PermissionError as perm_e:
         logger.error(f"[bold red]Permission Error: {perm_e}. Ensure files are not open and permissions are correct.[/bold red]", exc_info=True)
         _write_fatal_error(perm_e)
    except ImportError as imp_e:
         logger.error(f"[bold red]Import Error: {imp_e}. Ensure all dependencies are installed (pip install -r requirements.txt). Run as 'python -m coi_auditor.main'[/bold red]", exc_info=True)
         _write_fatal_error(imp_e)
    except Exception as e:
        logger.error(f"[bold red]An unexpected error occurred during the audit process: {e}[/bold red]", exc_info=True)
        _write_fatal_error(e)

def _write_fatal_error(exc):
    import traceback
    # Use the consistently defined logs_dir_path from the logging setup
    err_path = default_log_file.parent / 'fatal_error.txt' # Use default_log_file's parent
    try:
        with open(str(err_path), 'w', encoding='utf-8') as f: # open expects string path
            f.write('FATAL ERROR DURING AUDIT\n')
            f.write(traceback.format_exc())
        logger.info(f"Fatal error details written to: [cyan]{err_path}[/cyan]")
    except Exception as file_exc:
        # Use logger here if possible, though print is a fallback if logging itself failed
        logger.error(f"[bold red]Could not write fatal error file to {err_path}: {file_exc}[/bold red]")
        print(f"CRITICAL: Could not write fatal error file to {err_path}: {file_exc}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="COI Auditor: Process COI PDFs and validate.")
    parser.add_argument(
        "--validate-batch",
        metavar="FIXTURES_DIRECTORY",
        type=str,
        help="Run validation harness on all PDFs in the specified directory."
    )
    parser.add_argument(
        "--diagnose-pdf",
        metavar="PDF_FILE_PATH",
        type=str,
        help="Run diagnostic OCR on a single PDF and output the raw text."
    )
    parser.add_argument(
        "--debug-single-pdf",
        metavar="PDF_FILE_PATH",
        type=str,
        help="Process a single PDF with detailed debug output for date tokens and table snippets."
    )
    
    args = parser.parse_args()

    config = load_config() # Load config early for all modes

    if args.debug_single_pdf:
        logger.info(f"Debug mode triggered for PDF: [cyan]{args.debug_single_pdf}[/cyan]")
        run_debug_single_pdf(args.debug_single_pdf, config)
        # run_debug_single_pdf will sys.exit()

    if args.diagnose_pdf:
        logger.info(f"Diagnostic mode triggered for PDF: [cyan]{args.diagnose_pdf}[/cyan]")
        run_diagnostic_pdf_ocr(args.diagnose_pdf, config)
        # run_diagnostic_pdf_ocr will sys.exit()

    if args.validate_batch:
        os.environ['COI_VALIDATION_MODE'] = '1'
        logger.info("COI_VALIDATION_MODE environment variable set due to --validate-batch flag.")


    if args.validate_batch:
        fixtures_target_path = Path("tests/fixtures/")
        if not fixtures_target_path.exists():
            logger.warning(f"[yellow]Recommended fixtures directory '{fixtures_target_path}' does not exist. Please create it and add test PDFs.[/yellow]")
        elif not any(fixtures_target_path.glob('*.pdf')) and Path(args.validate_batch) == fixtures_target_path:
             logger.warning(f"[yellow]Fixtures directory '{fixtures_target_path}' is empty. Add PDFs for validation.[/yellow]")
        
        run_batch_validation(args.validate_batch)
    elif not args.diagnose_pdf and not args.debug_single_pdf: # Only run full audit if not in other modes
        run_audit()
