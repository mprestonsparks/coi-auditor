import os
from dotenv import load_dotenv
import pdfplumber

def scan_pdf_text_extraction():
    # .env file is in the project root, one level up from the 'tests' directory
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dotenv_path = os.path.join(project_root, '.env')
    load_dotenv(dotenv_path=dotenv_path)
    pdf_dir = os.getenv('PDF_DIRECTORY_PATH')
    assert pdf_dir and os.path.isdir(pdf_dir), f"PDF directory not found at {pdf_dir}"
    pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
    results = []
    for f in pdf_files:
        pdf_path = os.path.join(pdf_dir, f)
        try:
            with pdfplumber.open(pdf_path) as pdf:
                has_text = False
                for page in pdf.pages:
                    if page.extract_text():
                        has_text = True
                        break
                results.append((f, has_text))
        except Exception as e:
            results.append((f, False, str(e)))
    text_count = sum(1 for r in results if r[1] is True)
    print(f"PDFs with extractable text: {text_count} / {len(pdf_files)}")
    for r in results:
        print(f"{r[0]}: {'TEXT' if r[1] else 'NO TEXT'}" + (f" | ERROR: {r[2]}" if len(r) > 2 else ''))

if __name__ == '__main__':
    scan_pdf_text_extraction()
