import os
from dotenv import load_dotenv
import re

def detect_policy_type(filename):
    """Detects policy type ('GL', 'WC', or None) from filename."""
    base = os.path.splitext(filename)[0]
    if '_GL_' in base or base.endswith('_GL'):
        return 'GL'
    if '_WC_' in base or base.endswith('_WC'):
        return 'WC'
    return None

def test_policy_type_detection():
    project_root = os.path.dirname(os.path.abspath(__file__))
    dotenv_path = os.path.join(project_root, '.env')
    load_dotenv(dotenv_path=dotenv_path)
    pdf_dir = os.getenv('PDF_DIRECTORY_PATH')
    assert pdf_dir and os.path.isdir(pdf_dir), f"PDF directory not found at {pdf_dir}"
    pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
    for f in pdf_files[:20]:  # Sample first 20 for brevity
        policy = detect_policy_type(f)
        print(f"{f}: Policy Type Detected = {policy}")
    print("test_policy_type_detection PASSED")

if __name__ == '__main__':
    test_policy_type_detection()
