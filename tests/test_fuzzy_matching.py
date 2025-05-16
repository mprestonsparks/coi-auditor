import os
from dotenv import load_dotenv
import difflib
import openpyxl

def normalize(name):
    return ''.join(filter(str.isalnum, name)).lower() if name else ''

def test_fuzzy_matching():
    """Test fuzzy matching between Excel names and PDF filenames, log all candidates and scores."""
    project_root = os.path.dirname(os.path.abspath(__file__))
    dotenv_path = os.path.join(project_root, '.env')
    load_dotenv(dotenv_path=dotenv_path)

    excel_path = os.getenv('EXCEL_FILE_PATH')
    pdf_dir = os.getenv('PDF_DIRECTORY_PATH')
    assert excel_path and os.path.exists(excel_path), f"Excel file not found at {excel_path}"
    assert pdf_dir and os.path.isdir(pdf_dir), f"PDF directory not found at {pdf_dir}"

    wb = openpyxl.load_workbook(excel_path)
    sheet = wb.active
    header_row = int(os.getenv('EXCEL_HEADER_ROW', '1'))
    name_col = os.getenv('EXCEL_SUBCONTRACTOR_NAME_COL', 'Subcontractor Name')
    headers = [cell.value for cell in sheet[header_row]]
    name_idx = headers.index(name_col) + 1
    excel_names = [sheet.cell(row=r, column=name_idx).value for r in range(header_row+1, sheet.max_row+1)]
    excel_names = [n for n in excel_names if n]

    pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
    pdf_bases = [os.path.splitext(f)[0] for f in pdf_files]
    normalized_pdf_bases = [normalize(b) for b in pdf_bases]

    threshold = 0.8
    results = []
    for excel_name in excel_names[:10]:  # Sample first 10 for speed
        norm_excel = normalize(excel_name)
        scored = [(pdf_files[i], difflib.SequenceMatcher(None, norm_excel, normalized_pdf_bases[i]).ratio())
                  for i in range(len(pdf_files))]
        scored.sort(key=lambda x: x[1], reverse=True)
        best = [s for s in scored if s[1] >= threshold]
        results.append((excel_name, best[:3]))
        print(f"Excel: '{excel_name}' | Top matches: {best[:3]}")
    assert results, "No fuzzy matching results produced."
    print("test_fuzzy_matching PASSED")

if __name__ == '__main__':
    test_fuzzy_matching()
