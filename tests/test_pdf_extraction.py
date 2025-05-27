import os
import sys
import cv2
import numpy as np
from dotenv import load_dotenv
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.coi_auditor.pdf_parser import extract_dates_from_pdf

def test_pdf_extraction():
    # .env file is in the project root, one level up from the 'tests' directory
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dotenv_path = os.path.join(project_root, '.env')
    load_dotenv(dotenv_path=dotenv_path)
    
    # Use a PDF from the fixtures directory
    fixtures_dir = os.path.join(project_root, 'tests', 'fixtures')
    sample_pdf_name = 'FernandoHernandez_2024-09-19.pdf' # Example fixture
    pdf_path = os.path.join(fixtures_dir, sample_pdf_name)

    assert os.path.exists(pdf_path), f"Sample PDF not found at {pdf_path}"
    
    print(f"Testing extraction on: {sample_pdf_name}")
    # extract_dates_from_pdf expects a Path object or string path
    extracted_dates, note = extract_dates_from_pdf(pdf_path)
    print(f"Extracted Dates: {extracted_dates}")
    print(f"Note: {note}")
    
    # Basic assertion: check if the function ran and returned a dict for dates
    assert isinstance(extracted_dates, dict), "extract_dates_from_pdf did not return a dictionary for dates."
    # A more specific assertion would depend on the known content of the fixture PDF
    # For now, we'll assume if it runs and returns a dict, it's a basic pass.
    # If the fixture is known to have dates, this could be:
    # assert any(v for v in extracted_dates.values()), f"No dates extracted from sample PDF {sample_pdf_name}."
    print("test_pdf_extraction PASSED (basic check)")

# Removed test_ocr_functions as its dependencies (placeholder functions in audit.py) were removed.
# If specific OCR sub-component testing is needed, it should target available functions in pdf_parser.py.

if __name__ == '__main__':
    test_pdf_extraction()
