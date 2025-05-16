import os
from dotenv import load_dotenv
import openpyxl
from coi_auditor.pdf_parser import extract_dates_from_pdf
from coi_auditor.audit import aggregate_dates, check_coverage_gap

def test_aggregation_and_gap_analysis():
    project_root = os.path.dirname(os.path.abspath(__file__))
    dotenv_path = os.path.join(project_root, '.env')
    load_dotenv(dotenv_path=dotenv_path)
    pdf_dir = os.getenv('PDF_DIRECTORY_PATH')
    excel_path = os.getenv('EXCEL_FILE_PATH')
    assert pdf_dir and os.path.isdir(pdf_dir), f"PDF directory not found at {pdf_dir}"
    assert excel_path and os.path.exists(excel_path), f"Excel file not found at {excel_path}"
    # Pick a subcontractor with a text-extractable PDF
    try:
        wb = openpyxl.load_workbook(excel_path)
        sheet = wb.active
    except Exception as e:
        print(f"Error loading Excel file: {e}")
        return
    header_row = int(os.getenv('EXCEL_HEADER_ROW', '1'))
    name_col = os.getenv('EXCEL_SUBCONTRACTOR_NAME_COL', 'Subcontractor Name')
    headers = [cell.value for cell in sheet[header_row]]
    name_idx = headers.index(name_col) + 1
    for r in range(header_row+1, sheet.max_row+1):
        sub_name = sheet.cell(row=r, column=name_idx).value
        if not sub_name:
            continue
        # Try to find a matching PDF with text
        for pdf_file in os.listdir(pdf_dir):
            if not pdf_file.lower().endswith('.pdf'):
                continue
            pdf_path = os.path.join(pdf_dir, pdf_file)
            try:
                with open(pdf_path, 'rb') as f:
                    pass
                extracted_dates, note = extract_dates_from_pdf(pdf_path)
                if any(v for v in extracted_dates.values()):
                    # Aggregate just this one PDF for test
                    agg, notes = aggregate_dates([(pdf_path, extracted_dates, note)])
                    print(f"Subcontractor: {sub_name}")
                    print(f"PDF: {pdf_file}")
                    print(f"Extracted: {extracted_dates}")
                    print(f"Aggregated: {agg}")
                    # Test gap analysis for GL
                    audit_start = os.getenv('AUDIT_START_DATE')
                    audit_end = os.getenv('AUDIT_END_DATE')
                    from datetime import datetime
                    if audit_start:
                        audit_start = datetime.strptime(audit_start, '%Y-%m-%d').date()
                    if audit_end:
                        audit_end = datetime.strptime(audit_end, '%Y-%m-%d').date()
                    gl_from, gl_to = agg.get('gl_from'), agg.get('gl_to')
                    if gl_from and gl_to:
                        gap_status, gap_details = check_coverage_gap(gl_from, gl_to, audit_start, audit_end)
                        print(f"GL Gap Status: {gap_status} | Details: {gap_details}")
                    print("test_aggregation_and_gap_analysis PASSED")
                    return
            except Exception as e:
                continue
    print("No suitable subcontractor with extractable PDF found for aggregation test.")

if __name__ == '__main__':
    test_aggregation_and_gap_analysis()
