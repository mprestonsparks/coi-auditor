import os
from dotenv import load_dotenv

def test_env_and_config():
    """Test that .env exists, loads, and all required paths are present and valid."""
    # .env file is in the project root, one level up from the 'tests' directory
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dotenv_path = os.path.join(project_root, '.env')
    assert os.path.exists(dotenv_path), f".env file not found at {dotenv_path}"
    load_dotenv(dotenv_path=dotenv_path)

    excel_path = os.getenv('EXCEL_FILE_PATH')
    pdf_dir = os.getenv('PDF_DIRECTORY_PATH')
    output_dir = os.getenv('OUTPUT_DIRECTORY_PATH')

    assert excel_path and os.path.exists(excel_path), f"Excel file not found at {excel_path}"
    assert pdf_dir and os.path.isdir(pdf_dir), f"PDF directory not found at {pdf_dir}"
    assert output_dir and os.path.isdir(output_dir), f"Output directory not found at {output_dir}"
    print("test_env_and_config PASSED")

if __name__ == '__main__':
    test_env_and_config()
