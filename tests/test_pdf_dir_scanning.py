import os
from dotenv import load_dotenv

def test_pdf_dir_scanning():
    """Test that the PDF directory exists, is accessible, and all PDF files are listed and normalized."""
    # .env file is in the project root, one level up from the 'tests' directory
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dotenv_path = os.path.join(project_root, '.env')
    load_dotenv(dotenv_path=dotenv_path)

    pdf_dir = os.getenv('PDF_DIRECTORY_PATH')
    assert pdf_dir and os.path.isdir(pdf_dir), f"PDF directory not found at {pdf_dir}"
    pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
    assert pdf_files, f"No PDF files found in directory {pdf_dir}"
    # Normalize: remove extension, lowercase, alphanumeric only
    def normalize(name):
        return ''.join(filter(str.isalnum, os.path.splitext(name)[0])).lower()
    normalized = [normalize(f) for f in pdf_files]
    assert all(normalized), "Normalization failed for one or more PDF filenames."
    print(f"test_pdf_dir_scanning PASSED: {len(pdf_files)} PDFs found and normalized.")

if __name__ == '__main__':
    test_pdf_dir_scanning()
