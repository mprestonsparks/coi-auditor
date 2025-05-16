import os
import openpyxl
from dotenv import load_dotenv

def test_excel_loading():
    """Test that the Excel file can be loaded and required columns are present."""
    project_root = os.path.dirname(os.path.abspath(__file__))
    dotenv_path = os.path.join(project_root, '.env')
    load_dotenv(dotenv_path=dotenv_path)

    excel_path = os.getenv('EXCEL_FILE_PATH')
    assert excel_path and os.path.exists(excel_path), f"Excel file not found at {excel_path}"
    wb = openpyxl.load_workbook(excel_path)
    sheet = wb.active

    # Get headers from first non-empty row (default: row 1 unless overridden)
    header_row = int(os.getenv('EXCEL_HEADER_ROW', '1'))
    headers = [cell.value for cell in sheet[header_row]]
    required_cols = [os.getenv('EXCEL_SUBCONTRACTOR_NAME_COL', 'Subcontractor Name')]
    for col in required_cols:
        assert col in headers, f"Required column '{col}' not found in Excel headers: {headers}"
    print("test_excel_loading PASSED")

if __name__ == '__main__':
    test_excel_loading()
