"""
Utility script to extract and print all text content from a given PDF file.
Can be called with a PDF path as a command-line argument, or it defaults
to a test PDF in the `tests/fixtures` directory.
"""
import os
import pdfplumber
import sys
from pathlib import Path

def dump_pdf_text(pdf_full_path: Path):
    """
    Opens a PDF file and prints the extracted text from each page.

    Args:
        pdf_full_path: The absolute Path object to the PDF file.
    """
    if not pdf_full_path.is_file():
        print(f"Error: PDF file not found at {pdf_full_path}")
        return

    print(f"Dumping text for: {pdf_full_path.name}")
    try:
        with pdfplumber.open(pdf_full_path) as pdf:
            if not pdf.pages:
                print(f"Warning: PDF file '{pdf_full_path.name}' has no pages or is empty.")
                return
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                print(f"\n--- Page {i+1} of {len(pdf.pages)} ---\n")
                if text:
                    print(text)
                else:
                    print("(No text extracted from this page)")
    except Exception as e:
        print(f"Error processing PDF {pdf_full_path.name}: {e}")

if __name__ == '__main__':
    # Default PDF path construction
    script_dir = Path(__file__).resolve().parent
    # Default target is ../../tests/fixtures/X-Stream Cleaning_2025-01-07.pdf
    default_pdf_path = script_dir.parent.parent / "tests" / "fixtures" / "X-Stream Cleaning_2025-01-07.pdf"
    
    pdf_to_process: Path

    if len(sys.argv) > 1:
        arg_path = Path(sys.argv[1])
        if arg_path.is_absolute():
            pdf_to_process = arg_path
        else:
            # Assume relative to current working directory if not absolute
            pdf_to_process = Path.cwd() / arg_path
    else:
        pdf_to_process = default_pdf_path
    
    dump_pdf_text(pdf_to_process.resolve())
