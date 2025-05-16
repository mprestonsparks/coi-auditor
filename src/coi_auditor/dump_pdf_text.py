import os
# from dotenv import load_dotenv # No longer needed for direct path
import pdfplumber
import sys # To accept command line arguments

def dump_pdf_text(pdf_full_path): # Modified signature
    # project_root = os.path.dirname(os.path.abspath(__file__)) # Not needed
    # dotenv_path = os.path.join(project_root, '.env') # Not needed
    # load_dotenv(dotenv_path=dotenv_path) # Not needed
    # pdf_dir = os.getenv('PDF_DIRECTORY_PATH') # Not needed
    # assert pdf_dir and os.path.isdir(pdf_dir), f"PDF directory not found at {pdf_dir}" # Not needed
    # pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')] # Not needed
    # # Default to Armor-of-God-Construction_2024-08-19.pdf if present # Not needed
    # if not pdf_filename: # Not needed
    #     for f in pdf_files: # Not needed
    #         if 'Armor-of-God-Construction_2024-08-19.pdf' in f: # Not needed
    #             pdf_filename = f # Not needed
    #             break # Not needed
    #     else: # Not needed
    #         pdf_filename = pdf_files[0] # Not needed
    
    pdf_path = pdf_full_path # Use the direct path
    if not os.path.isfile(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        return

    print(f"Dumping text for: {os.path.basename(pdf_path)}") # Use basename for cleaner log
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            print(f"\n--- Page {i+1} ---\n{text}")

if __name__ == '__main__':
    # Construct the path to the target PDF relative to this script's location
    # Script is in src/coi_auditor/
    # PDF is in tests/fixtures/
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Corrected relative path for Windows, ensuring forward slashes for os.path.join consistency
    # or using Path objects if preferred for robustness.
    # Using os.path.normpath to ensure correct path separators for the OS.
    target_pdf_relative_path = os.path.normpath('../../tests/fixtures/X-Stream Cleaning_2025-01-07.pdf')
    target_pdf_full_path = os.path.join(script_dir, target_pdf_relative_path)
    
    # Allow overriding with a command-line argument
    if len(sys.argv) > 1:
        pdf_to_dump = sys.argv[1]
        if not os.path.isabs(pdf_to_dump): # If relative path given, make it absolute from CWD
             pdf_to_dump = os.path.abspath(pdf_to_dump)
        dump_pdf_text(pdf_to_dump)
    else:
        dump_pdf_text(target_pdf_full_path)
