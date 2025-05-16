import os
import sys
import cv2
import numpy as np
from dotenv import load_dotenv
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.coi_auditor.pdf_parser import extract_dates_from_pdf

def test_pdf_extraction():
    project_root = os.path.dirname(os.path.abspath(__file__))
    dotenv_path = os.path.join(project_root, '.env')
    load_dotenv(dotenv_path=dotenv_path)
    pdf_dir = os.getenv('PDF_DIRECTORY_PATH')
    assert pdf_dir and os.path.isdir(pdf_dir), f"PDF directory not found at {pdf_dir}"
    pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
    assert pdf_files, f"No PDF files found in directory {pdf_dir}"
    sample_pdf = 'Armor-of-God-Construction_2024-08-19.pdf'
    pdf_path = os.path.join(pdf_dir, sample_pdf)
    print(f"Testing extraction on: {sample_pdf}")
    extracted_dates, note = extract_dates_from_pdf(pdf_path)
    print(f"Extracted Dates: {extracted_dates}")
    print(f"Note: {note}")
    assert any(v for v in extracted_dates.values()), "No dates extracted from sample PDF."
    print("test_pdf_extraction PASSED")

def test_ocr_functions():
    from src.coi_auditor.audit import preprocess_date_region, extract_date_text, validate_and_normalize_date

    # Create a dummy image
    img = np.zeros((100, 200, 3), dtype=np.uint8)
    cv2.putText(img, "01/01/2025", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    # Preprocess the image
    preprocessed_img = preprocess_date_region(img)

    # Extract text from the image
    extracted_text = extract_date_text(preprocessed_img, ocr_engine='tesseract')
    print(f"Extracted text: {extracted_text}")

    # Validate and normalize the date
    normalized_date = validate_and_normalize_date(extracted_text)
    print(f"Normalized date: {normalized_date}")

    assert normalized_date == "2025-01-01", "Date normalization failed"
    print("test_ocr_functions PASSED")

if __name__ == '__main__':
    test_pdf_extraction()
    test_ocr_functions()
