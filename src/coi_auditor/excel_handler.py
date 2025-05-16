"""Handles reading and writing data to the Excel subcontractor list."""

import openpyxl
import csv
import os
from datetime import date
import datetime # Added for type hinting if needed, and robust date handling
import logging
import gc
from pathlib import Path # Added for type hinting
from openpyxl.utils import column_index_from_string
from openpyxl.utils import get_column_letter
from openpyxl.styles import PatternFill, Font

# Define expected/output column headers
# Input columns (expected, but now configurable via .env)
SUBCONTRACTOR_ID_COL = 'Subcontractor ID'  # Optional, used if present

# Output columns (will be created/updated) - These match the Excel column headers
GL_FROM_COL = 'GL_FROM_COL'  # Column I - GL From date
GL_TO_COL = 'GL_TO_COL'      # Column J - GL To date
WC_FROM_COL = 'WC_FROM_COL'  # Column K - WC From date
WC_TO_COL = 'WC_TO_COL'      # Column L - WC To date

# Additional outputs for gaps reporting
GL_GAP_COL = 'GL Coverage Gap'
WC_GAP_COL = 'WC Coverage Gap'
NOTES_COL = 'Audit Notes'

GL_OUTPUT_COLUMNS = [GL_FROM_COL, GL_TO_COL]
WC_OUTPUT_COLUMNS = [WC_FROM_COL, WC_TO_COL]
GAP_OUTPUT_COLUMNS = [GL_GAP_COL, WC_GAP_COL, NOTES_COL]


def _find_last_nonempty_row(sheet, col_idx, start_row, max_row):
    """Find last non-empty row in the specified column (from bottom up)."""
    for row in range(max_row, start_row - 1, -1):
        val = sheet.cell(row=row, column=col_idx).value
        if val and str(val).strip():
            return row
    return start_row - 1  # If all empty, return before start


def read_subcontractors(excel_path):
    """Reads subcontractor data from the specified Excel file, specifically from the 'SUMMARY' worksheet."""
    import os
    import traceback
    subcontractors = []
    try:
        logging.info(f"[read_subcontractors] Attempting to read Excel file: {excel_path}")
        # Read environment variables here, after .env is loaded
        header_row = int(os.getenv('EXCEL_HEADER_ROW', '6'))  # Default header row is 6 per SUMMARY sheet structure
        subcontractor_name_col = os.getenv('EXCEL_SUBCONTRACTOR_NAME_COL', 'Name')  # SUMMARY sheet column header is 'Name'
        subcontractor_id_col = 'Subcontractor ID'  # Optional, used only if present in headers
        logging.info(f"[read_subcontractors] header_row: {header_row}, subcontractor_name_col: {subcontractor_name_col}, subcontractor_id_col: {subcontractor_id_col}")

        workbook = openpyxl.load_workbook(excel_path, data_only=True) # data_only=True to get values, not formulas
        if 'SUMMARY' not in workbook.sheetnames:
            raise Exception("Required worksheet 'SUMMARY' not found in workbook. Please ensure the Excel file has a worksheet named 'SUMMARY'.")
        sheet = workbook['SUMMARY']
        logging.info(f"[read_subcontractors] Loaded 'SUMMARY' worksheet. sheet.max_row={sheet.max_row}")
        
        # Read headers from the configured header row
        headers = [cell.value for cell in sheet[header_row]]
        for idx, val in enumerate(headers):
            logging.info(f"Header cell {idx+1}: {repr(val)}")
        logging.info(f"Excel headers found (row {header_row}): {headers}")

        # Validate essential input column
        if subcontractor_name_col not in headers:
            raise ValueError(f"Missing required column '{subcontractor_name_col}' in Excel file: {excel_path}")

        name_col_idx = headers.index(subcontractor_name_col)
        id_col_idx = headers.index(subcontractor_id_col) if subcontractor_id_col in headers else None
        logging.info(f"[read_subcontractors] name_col_idx: {name_col_idx}, id_col_idx: {id_col_idx}")

        # Determine subcontractor flag column (defaults to column C / index 2)
        flag_col_env = os.getenv('EXCEL_SUBCONTRACTOR_FLAG_COL')  # Can be a letter (e.g., 'C') or 1-based index (e.g., '3')
        flag_col_idx = None
        if flag_col_env and flag_col_env.strip():
            try:
                if flag_col_env.strip().isdigit():
                    flag_col_idx = int(flag_col_env.strip()) - 1  # Convert to 0-based
                else:
                    flag_col_idx = column_index_from_string(flag_col_env.strip().upper()) - 1
            except Exception as e:
                logging.warning(f"Invalid EXCEL_SUBCONTRACTOR_FLAG_COL value '{flag_col_env}': {e}. Falling back to auto-detection.")

        # Auto-detect by header name if env var not provided / invalid
        if flag_col_idx is None:
            for idx, hdr in enumerate(headers):
                if hdr and str(hdr).strip().lower() in ("subcontractor", "subcontractor?", "is subcontractor", "sub?", "sub flag"):
                    flag_col_idx = idx
                    break
        # Final fallback to column C (index 2)
        if flag_col_idx is None:
            flag_col_idx = 2
        logging.info(f"[read_subcontractors] subcontractor_flag_col_idx: {flag_col_idx}")

        # Determine last data row
        last_row_env = os.getenv('EXCEL_LAST_DATA_ROW')
        if last_row_env and last_row_env.strip():
            try:
                last_data_row = int(last_row_env)
                if last_data_row < header_row:
                    raise ValueError(f"EXCEL_LAST_DATA_ROW ({last_data_row}) cannot be before header row ({header_row})!")
            except Exception as e:
                raise ValueError(f"Invalid EXCEL_LAST_DATA_ROW value: {last_row_env}. Error: {e}")
        else:
            # Auto-detect last non-empty row
            last_data_row = _find_last_nonempty_row(sheet, name_col_idx+1, header_row+1, sheet.max_row)
        logging.info(f"[read_subcontractors] last_data_row: {last_data_row}, sheet.max_row: {sheet.max_row}")
        if last_data_row > sheet.max_row:
            raise ValueError(f"EXCEL_LAST_DATA_ROW ({last_data_row}) exceeds Excel sheet max row ({sheet.max_row})!")
        if last_data_row - header_row > 100000:
            raise ValueError(f"Sanity check failed: last_data_row-header_row > 100,000. This would process too many rows. Check your Excel file and .env settings.")

        # Data starts on the row after the header
        for row_idx in range(header_row + 1, last_data_row + 1):
            sub_name_cell = sheet.cell(row=row_idx, column=name_col_idx + 1)
            sub_name = sub_name_cell.value

            # Check subcontractor flag first
            flag_val = sheet.cell(row=row_idx, column=flag_col_idx + 1).value
            if not flag_val or str(flag_val).strip().lower() not in ("yes", "y", "true", "1"):
                logging.info(f"Skipping non-subcontractor row {row_idx} (flag value: {flag_val})")
                continue

            if not sub_name or not str(sub_name).strip():  # Skip rows with no subcontractor name
                logging.warning(f"Skipping empty row {row_idx} in Excel file.")
                continue

            sub_name = str(sub_name).strip()
            if id_col_idx is not None:
                cell_value = sheet.cell(row=row_idx, column=id_col_idx + 1).value
                sub_id = str(cell_value).strip() if cell_value else f"ROW_{row_idx}"
            else:
                sub_id = f"ROW_{row_idx}"

            subcontractors.append({
                'row': row_idx,  # Keep track of original row for updates
                'name': sub_name,
                'id': sub_id,
            })

        logging.info(f"Read {len(subcontractors)} subcontractors from {excel_path}")
        if not subcontractors:
            logging.warning(f"No subcontractors found in {excel_path}. Please check the file and '{subcontractor_name_col}' column.")

        return subcontractors, headers
    except Exception as e:
        logging.error(f"[read_subcontractors] Exception: {e}\n{traceback.format_exc()}")
        raise Exception(f"Error reading Excel file {excel_path}: {e}")


    except FileNotFoundError:
        logging.error(f"Excel file not found at: {excel_path}")
        raise
    except Exception as e:
        logging.error(f"Error reading Excel file {excel_path}: {e}")
        raise Exception(f"Error reading Excel file {excel_path}: {e}")

def get_output_sheet(workbook, output_sheet_name=None):
    """
    Returns a worksheet for output. ONLY uses the 'SUMMARY' worksheet as the base. If output_sheet_name is set and not 'SUMMARY', creates a copy from 'SUMMARY'.
    Will raise an error if 'export' worksheet is present to prevent accidental usage.
    """
    base_sheet_name = 'SUMMARY'
    if 'export' in workbook.sheetnames:
        raise Exception("The 'export' worksheet is present in the workbook. Please remove it to avoid accidental usage. Only 'SUMMARY' should be used as the worksheet basis.")
    if base_sheet_name not in workbook.sheetnames:
        raise Exception("Could not find 'SUMMARY' worksheet in the workbook. Please ensure your Excel file contains a worksheet named 'SUMMARY'.")
    base = workbook[base_sheet_name]
    output_sheet_name = output_sheet_name or os.getenv('EXCEL_OUTPUT_SHEET', 'SUMMARY')
    write_policy_dates = os.getenv('WRITE_POLICY_DATES', 'false').lower() in ('1', 'true', 'yes', 'on')
    # If outputting to a different sheet, always copy from SUMMARY (never from export)
    if write_policy_dates and output_sheet_name != base_sheet_name:
        if output_sheet_name in workbook.sheetnames:
            return workbook[output_sheet_name]
        new_sheet = workbook.copy_worksheet(base)
        new_sheet.title = output_sheet_name
        logging.info(f"Created output worksheet '{output_sheet_name}' as a copy of '{base.title}' (never from 'export')")
        return new_sheet
    # Default: just use SUMMARY sheet directly
    logging.info(f"Using 'SUMMARY' worksheet for all output.")
    return base

def insert_gap_rows(sheet, result, col_map):
    """
    For each gap in result['gl_gap_ranges'] and result['wc_gap_ranges'], insert a row below the subcontractor row.
    No custom formatting is applied to inserted rows (plain rows only).
    """
    row_idx = result.get('row')
    name = result.get('name', '')
    sub_id = result.get('id', '')
    
    # Find the name and ID columns from the first row
    name_col = 1  # Default to column A
    id_col = 3    # Default to column C
    
    # Look at headers in row 6 to find the correct columns
    for col_idx in range(1, 10):  # Check first 10 columns
        header = sheet.cell(row=6, column=col_idx).value
        if header and 'name' in str(header).lower():
            name_col = col_idx
        if header and 'id' in str(header).lower() and 'subcontractor' in str(header).lower():
            id_col = col_idx
    
    gap_types = [('GL', 'gl_gap_ranges'), ('WC', 'wc_gap_ranges')]
    for gap_type, key in gap_types:
        for gap in result.get(key, []):
            # Insert a new row below the main row
            sheet.insert_rows(row_idx + 1)
            
            # Copy name and ID to identify the subcontractor
            sheet.cell(row=row_idx + 1, column=name_col).value = name
            if id_col:
                sheet.cell(row=row_idx + 1, column=id_col).value = sub_id
            
            # Add gap information
            # For GL gaps, write in the GL date columns
            if gap_type == 'GL':
                sheet.cell(row=row_idx + 1, column=col_map[GL_FROM_COL]).value = gap[0]
                sheet.cell(row=row_idx + 1, column=col_map[GL_TO_COL]).value = gap[1]
                if NOTES_COL in col_map:
                    sheet.cell(row=row_idx + 1, column=col_map[NOTES_COL]).value = "GL Coverage Gap"
            # For WC gaps, write in the WC date columns
            elif gap_type == 'WC':
                sheet.cell(row=row_idx + 1, column=col_map[WC_FROM_COL]).value = gap[0]
                sheet.cell(row=row_idx + 1, column=col_map[WC_TO_COL]).value = gap[1]
                if NOTES_COL in col_map:
                    sheet.cell(row=row_idx + 1, column=col_map[NOTES_COL]).value = "WC Coverage Gap"
            
            # No custom formatting: inserted gap row is plain
            row_idx += 1  # Next gap row is always below the last one

def update_excel(excel_path, results, headers):
    """Updates the Excel file with audit results and, if enabled, writes policy dates and gap rows to a summary sheet."""
    try:
        workbook = openpyxl.load_workbook(excel_path)
        write_policy_dates = os.getenv('WRITE_POLICY_DATES', 'false').lower() in ('1', 'true', 'yes', 'on')
        
        # Always use SUMMARY sheet or create a copy if needed
        sheet = get_output_sheet(workbook)
        
        # Map GL and WC columns based on the spreadsheet layout shown in the image
        # In the sample image:
        # - GL dates: columns I(9) and J(10) (From/To)
        # - WC dates: columns K(11) and L(12) (From/To)
        
        # Use fixed columns from the image - no dynamic detection needed
        # This ensures we always write to the correct columns regardless of headers
        col_map = {
            'GL_FROM_COL': 9,    # Column I - GL From date
            'GL_TO_COL': 10,    # Column J - GL To date
            'WC_FROM_COL': 11,  # Column K - WC From date
            'WC_TO_COL': 12,    # Column L - WC To date
        }
        logging.info(f"Using fixed column mapping: GL_FROM_COL=I(9), GL_TO_COL=J(10), WC_FROM_COL=K(11), WC_TO_COL=L(12)")
        
        # Only map the fixed columns for SUMMARY (I/J/K/L)
        # No audit/gap columns or gap rows will be added to SUMMARY
        update_count = 0
        for result in sorted(results, key=lambda x: x.get('row', 0), reverse=True):
            row_idx = result.get('row')
            if not row_idx:
                logging.warning(f"Skipping result with missing 'row' identifier: {result.get('name', 'N/A')}")
                continue
            def format_date_cell(dt):
                return dt if isinstance(dt, date) else None
            try:
                # Write only valid dates to GL and WC columns
                sheet.cell(row=row_idx, column=col_map['GL_FROM_COL']).value = format_date_cell(result.get('gl_from'))
                sheet.cell(row=row_idx, column=col_map['GL_TO_COL']).value = format_date_cell(result.get('gl_to'))
                sheet.cell(row=row_idx, column=col_map['WC_FROM_COL']).value = format_date_cell(result.get('wc_from'))
                sheet.cell(row=row_idx, column=col_map['WC_TO_COL']).value = format_date_cell(result.get('wc_to'))
                update_count += 1
            except Exception as cell_e:
                logging.error(f"Error updating cell for row {row_idx}, sub '{result.get('name', 'N/A')}': {cell_e}")
        try:
            workbook.save(excel_path)
            logging.info(f"Successfully updated {update_count} rows in {excel_path}")
            workbook.close() # Ensure workbook is closed
        except PermissionError:
            logging.error(f"Permission denied saving Excel file: {excel_path}. Ensure the file is not open.")
            raise Exception(f"Permission denied saving Excel file: {excel_path}. Please close the file and try again.")
        except Exception as save_e:
            logging.error(f"Failed to save Excel file {excel_path}: {save_e}")
            raise
    except Exception as e:
        logging.error(f"Error processing or updating Excel file {excel_path}: {e}")
        raise

def _apply_basic_formatting(worksheet, header_row_idx=1):
    """Applies basic formatting: bold header, auto-fit columns, freeze header row."""
    if not worksheet:
        logging.debug(f"Skipping formatting for empty or None worksheet object passed for title '{getattr(worksheet, 'title', 'N/A')}'.")
        return

    sheet_title = worksheet.title if hasattr(worksheet, 'title') else "UnknownSheet"
    logging.debug(f"Applying basic formatting to worksheet: '{sheet_title}' with header row {header_row_idx}.")

    # Bold Header
    bold_font = Font(bold=True)
    if worksheet.max_row >= header_row_idx and worksheet.max_column >= 1:
        try:
            # Ensure the row exists before iterating
            if header_row_idx <= worksheet.max_row:
                for cell in worksheet[header_row_idx]:
                    if cell:  # Ensure cell object exists
                        cell.font = bold_font
                logging.debug(f"Applied bold font to header row {header_row_idx} for sheet '{sheet_title}'.")
            else:
                logging.warning(f"Header row {header_row_idx} is out of bounds (max_row: {worksheet.max_row}) for sheet '{sheet_title}'. Skipping bolding.")
        except Exception as e: # Catching a broader exception for safety
            logging.warning(f"Could not apply bold font to header row {header_row_idx} for sheet '{sheet_title}': {e}", exc_info=True)
            # Decide if to return or continue with other formatting
            # For now, continue with other formatting attempts

    # Auto-fit Columns
    max_lengths = {}  # col_idx (1-based) -> max_length
    try:
        for col_idx, column_iter in enumerate(worksheet.iter_cols(min_row=1, max_row=worksheet.max_row, min_col=1, max_col=worksheet.max_column), 1):
            current_max_length = 0
            for cell in column_iter:
                if cell.value is not None:
                    try:
                        # Attempt to handle dates specifically for a more consistent length
                        if isinstance(cell.value, (datetime.date, datetime.datetime)):
                            # Common date/datetime string formats are around 10-19 chars
                            # e.g., "YYYY-MM-DD" (10), "YYYY-MM-DD HH:MM:SS" (19)
                            # We can set a typical length or use str() and let it be.
                            # For simplicity with "basic" formatting, str() is fine.
                            cell_value_str = str(cell.value)
                        else:
                            cell_value_str = str(cell.value)
                        current_max_length = max(current_max_length, len(cell_value_str))
                    except Exception as cell_str_err:
                        logging.debug(f"Could not convert cell value to string for length calculation in sheet '{sheet_title}', col {col_idx}: {cell_str_err}")
            if current_max_length > 0:
                max_lengths[col_idx] = current_max_length
    except Exception as e:
        logging.warning(f"Error during column width calculation for sheet '{sheet_title}': {e}", exc_info=True)

    if max_lengths:
        for col_idx, length in max_lengths.items():
            column_letter = get_column_letter(col_idx)
            # Add padding, cap at a reasonable max (e.g., 75) to prevent overly wide columns
            adjusted_width = min(length + 3, 75) # Increased padding slightly
            worksheet.column_dimensions[column_letter].width = adjusted_width
        logging.debug(f"Auto-fitted column widths for sheet '{sheet_title}'.")
    else:
        logging.debug(f"No content found to auto-fit column widths for sheet '{sheet_title}'.")


    # Freeze Header Row
    # Ensure there's at least one row below the header to freeze and the sheet is not empty
    if worksheet.max_row > header_row_idx and header_row_idx >= 1:
        try:
            # The cell to freeze panes at is the first cell of the row *below* the header
            pane_to_freeze_cell = worksheet.cell(row=header_row_idx + 1, column=1)
            worksheet.freeze_panes = pane_to_freeze_cell.coordinate # Use .coordinate
            logging.debug(f"Froze header row at {pane_to_freeze_cell.coordinate} for sheet '{sheet_title}'.")
        except Exception as e:
            logging.warning(f"Could not freeze panes for sheet '{sheet_title}': {e}", exc_info=True)
    elif worksheet.max_row == header_row_idx and header_row_idx >= 1 : # Only header row exists
        logging.debug(f"Skipping freeze panes for sheet '{sheet_title}' as it only contains the header row or is empty.")
    elif header_row_idx == 0 : # Invalid header row index for freezing
        logging.debug(f"Skipping freeze panes for sheet '{sheet_title}' due to invalid header_row_idx: {header_row_idx}.")


def write_gaps_report(output_dir, gaps, excel_path=None):
    """Writes the gap report to a CSV file, and writes GAPS_REPORT and ERRORS_REPORT worksheets to Excel if excel_path is provided."""
    import openpyxl
    report_path = os.path.join(output_dir, 'gaps_report.csv')
    if not gaps:
        logging.info("No gaps or issues found to report. Skipping CSV and worksheet generation.")
        return
    # Write CSV as before (all issues)
    try:
        fieldnames_standard = ['subcontractor_name', 'subcontractor_id', 'issue_type', 'details', 'coverage_type', 'gap_start', 'gap_end']
        all_gap_keys = set().union(*(d.keys() for d in gaps))
        fieldnames = list(dict.fromkeys(fieldnames_standard + sorted(list(all_gap_keys - set(fieldnames_standard)))))
        with open(report_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(gaps)
        logging.info(f"Gaps report saved to {report_path}")
    except PermissionError:
        logging.error(f"Permission denied writing gaps report: {report_path}. Check file permissions or if it's open.")
        raise
    except Exception as e:
        logging.error(f"Error writing gaps report to {report_path}: {e}")
        raise Exception(f"Error writing gaps report to {report_path}: {e}")
    # Write to Excel worksheets if excel_path provided
    if excel_path:
        try:
            workbook = openpyxl.load_workbook(excel_path)
            # GAPS_REPORT: only rows where issue_type == 'Gap', only selected columns
            gap_rows = [g for g in gaps if g.get('issue_type') == 'Gap']
            gap_fields = ['subcontractor_name', 'coverage_type', 'gap_start', 'gap_end']
            if 'GAPS_REPORT' in workbook.sheetnames:
                del workbook['GAPS_REPORT']
            ws_gap = workbook.create_sheet('GAPS_REPORT')
            for col_idx, field in enumerate(gap_fields, 1):
                ws_gap.cell(row=1, column=col_idx, value=field)
            for row_idx, gap in enumerate(gap_rows, 2):
                for col_idx, field in enumerate(gap_fields, 1):
                    ws_gap.cell(row=row_idx, column=col_idx, value=gap.get(field, ''))
            _apply_basic_formatting(ws_gap, header_row_idx=1) # Apply formatting
            logging.info(f"GAPS_REPORT worksheet created with {len(gap_rows)} gap rows.")
            # ERRORS_REPORT: all non-gap issues, with specific fields (excluding gap_start/end)
            error_rows = [g for g in gaps if g.get('issue_type') != 'Gap']
            if 'ERRORS_REPORT' in workbook.sheetnames:
                del workbook['ERRORS_REPORT']
            if error_rows:
                ws_err = workbook.create_sheet('ERRORS_REPORT')
                # Define headers for ERRORS_REPORT, excluding 'gap_start' and 'gap_end'
                error_report_headers = [f for f in fieldnames if f not in ['gap_start', 'gap_end']]
                
                for col_idx, field in enumerate(error_report_headers, 1):
                    ws_err.cell(row=1, column=col_idx, value=field)
                for row_idx, err in enumerate(error_rows, 2):
                    for col_idx, field in enumerate(error_report_headers, 1):
                        ws_err.cell(row=row_idx, column=col_idx, value=err.get(field, ''))
                _apply_basic_formatting(ws_err, header_row_idx=1) # Apply formatting
                logging.info(f"ERRORS_REPORT worksheet created with {len(error_rows)} error rows using filtered headers.")
            workbook.save(excel_path)
            logging.info(f"Gaps and errors worksheets written to {excel_path}")
            workbook.close() # Ensure workbook is closed
        except Exception as e:
            logging.error(f"Failed to write GAPS_REPORT or ERRORS_REPORT worksheet: {e}")
            raise Exception(f"Failed to write GAPS_REPORT or ERRORS_REPORT worksheet: {e}")


def run_excel_sanity_checks(excel_path=None):
    """Run basic sanity checks on Excel file and config. Abort if failed."""
    import sys
    import os
    import traceback
    if not excel_path:
        excel_path = os.getenv('EXCEL_FILE_PATH')
    if not excel_path or not os.path.exists(excel_path):
        print(f"Sanity check failed: Excel file not found at {excel_path}")
        sys.exit(1)
    try:
        # This will raise if bounds are insane or config is wrong
        read_subcontractors(excel_path)
        print("Excel sanity checks passed.")
    except Exception as e:
        print(f"Sanity check failed: {e}\n{traceback.format_exc()}")
        sys.exit(1)


def create_error_report_workbook_for_validation(output_path: Path, errors_data: list, headers: list):
    """
    Creates a new Excel workbook with an "ERROR_REPORT" sheet populated with
    the given errors_data and headers. This is used for the --validate-batch feature.

    Args:
        output_path: The Path where the Excel file will be saved.
        errors_data: A list of dictionaries, where each dictionary represents an error row.
                     The keys in the dictionary should correspond to the provided headers.
        headers: A list of strings representing the column headers for the "ERROR_REPORT" sheet.
    """
    logging.info(f"Creating error report workbook for validation at: {output_path}")
    workbook = openpyxl.Workbook()

    # Remove default sheet if it exists (usually named "Sheet")
    if "Sheet" in workbook.sheetnames:
        default_sheet = workbook["Sheet"]
        workbook.remove(default_sheet)
        logging.debug("Removed default 'Sheet' from new workbook.")

    error_sheet = workbook.create_sheet("ERROR_REPORT")
    logging.debug("Created 'ERROR_REPORT' sheet.")

    # Write headers
    for col_idx, header_title in enumerate(headers, 1):
        error_sheet.cell(row=1, column=col_idx, value=header_title)
    logging.debug(f"Wrote headers: {headers}")

    # Write error data
    for row_idx, error_item in enumerate(errors_data, 2): # Start data from row 2
        for col_idx, header_key in enumerate(headers, 1):
            cell_value = error_item.get(header_key, "") # Get value by header key
            error_sheet.cell(row=row_idx, column=col_idx, value=cell_value)
    _apply_basic_formatting(error_sheet, header_row_idx=1) # Apply formatting
    logging.debug(f"Wrote {len(errors_data)} error rows to 'ERROR_REPORT'.")

    try:
        workbook.save(output_path)
        logging.info(f"Successfully saved validation error report to: {output_path}")
        workbook.close() # Ensure workbook is closed
        gc.collect()
    except PermissionError:
        logging.error(f"Permission denied saving validation error report: {output_path}. Ensure the file is not open and permissions are correct.")
        # Re-raise to allow calling function to handle if needed
        raise
    except Exception as e:
        logging.error(f"Failed to save validation error report {output_path}: {e}", exc_info=True)
        # Re-raise
        raise


if __name__ == '__main__':
    # Basic test for running module directly (limited without actual files)
    print("Excel handler module - run main.py for full execution.")
    logging.basicConfig(level=logging.INFO) # Ensure logging works when run directly
    print(f"Expected input column: {SUBCONTRACTOR_ID_COL}")
    print(f"Optional input column: {SUBCONTRACTOR_ID_COL}")
    # print(f"Output columns: {', '.join(OUTPUT_COLUMNS)}") # OUTPUT_COLUMNS was not defined, commented out
    
    # Test for create_error_report_workbook_for_validation
    print("\nTesting create_error_report_workbook_for_validation...")
    test_headers = ["Col A", "Col B", "Col C"]
    test_data = [
        {"Col A": "Data1A", "Col B": "Data1B", "Col C": "Data1C"},
        {"Col A": "Data2A", "Col B": "Data2B", "Col C": "Data2C", "ExtraCol": "Should be ignored"},
        {"Col B": "Data3BOnly"} # Missing Col A and Col C
    ]
    test_output_path = Path("temp_validation_report_test.xlsx")
    try:
        create_error_report_workbook_for_validation(test_output_path, test_data, test_headers)
        # Verify content (basic check)
        wb_check = openpyxl.load_workbook(test_output_path)
        assert "ERROR_REPORT" in wb_check.sheetnames
        sheet_check = wb_check["ERROR_REPORT"]
        assert sheet_check.cell(row=1, column=1).value == "Col A"
        assert sheet_check.cell(row=2, column=1).value == "Data1A"
        assert sheet_check.cell(row=4, column=1).value is None # For {"Col B": "Data3BOnly"}
        assert sheet_check.cell(row=4, column=2).value == "Data3BOnly"
        print(f"Test report created at {test_output_path}. Please inspect manually.")
        # test_output_path.unlink() # Clean up
        print(f"Test successful. Cleaned up {test_output_path} (manual deletion might be needed if open).")

    except Exception as e:
        print(f"Test failed: {e}")
    finally:
        if test_output_path.exists():
             try:
                test_output_path.unlink() # Ensure cleanup
             except PermissionError:
                print(f"Could not delete {test_output_path} as it might be open.")
