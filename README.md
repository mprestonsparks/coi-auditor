# COI Auditor

This script automates the process of auditing Certificates of Insurance (COIs) for subcontractors.

## Features

- Reads subcontractor list from an Excel file.
- Scans a directory for COI PDF files associated with each subcontractor.
- Extracts General Liability (GL) and Workers' Compensation (WC) effective and expiration dates from PDFs.
- Aggregates coverage dates across multiple COIs for the same subcontractor.
- Identifies coverage gaps based on a defined audit period.
- Updates the original Excel file with audit findings.
- Generates a `gaps_report.csv` detailing any issues.

## Setup

1.  **Install dependencies:**
    To install the core application dependencies:
    ```bash
    pip install .
    ```
    For development, including tools for testing, linting, and running tasks, install with the `dev` extras:
    ```bash
    pip install .[dev]
    ```
    (This assumes `invoke`, `black`, and `pyright` are listed in `pyproject.toml` under `project.optional-dependencies.dev`).
    Alternatively, if you have a `requirements.txt` for core dependencies and `requirements-dev.txt` for development, use those. For now, we'll assume `pyproject.toml` is the source of truth.

2.  **Configure environment variables:**
    - Create a `.env` file in the project root by copying `.env.example`:
      ```bash
      cp .env.example .env
      ```
    - Update the required environment variables in your `.env` file:
      - `EXCEL_FILE_PATH`: Path to the subcontractor Excel file
      - `PDF_DIRECTORY_PATH`: Path to the directory containing COI PDFs
      - `OUTPUT_DIRECTORY_PATH`: Path for output files
      - `AUDIT_START_DATE`: Start date for the audit period
      - `AUDIT_END_DATE`: End date for the audit period
      - `POPPLER_BIN_PATH`: **Required** - Path to Poppler utilities bin directory (e.g., `C:\cli\poppler-24.08.0\Library\bin` on Windows)
      - `TESSERACT_CMD`: Optional - Path to Tesseract executable if not in system PATH
    - The `.env` file is used for environment-specific settings such as file paths, audit periods, and system-specific tool paths.
    - The `config.yaml` file defines application behavior settings including document parsing keywords, algorithm thresholds, OCR configurations, and folder structure settings. The application loads `config.yaml` first, and then settings from `.env` can override or supplement these.

3.  **Install system dependencies:**
    - **Poppler**: Required for PDF processing. Download from [Poppler releases](https://github.com/oschwartz10612/poppler-windows/releases/) and set `POPPLER_BIN_PATH` to the bin directory.
    - **Tesseract OCR**: Optional but recommended. Download from [Tesseract releases](https://github.com/tesseract-ocr/tesseract/releases) and either add to PATH or set `TESSERACT_CMD`.
4.  **Prepare input files:**
    - Ensure the Subcontractor Excel file exists at the specified path.
    - Ensure the COI PDFs are located in the specified directory, following naming conventions if applicable.

## Usage

To run the COI Auditor main application:
```bash
coi-auditor
```
Alternatively, you can use the task runner:
```bash
python tasks.py run
```

The script will process the files and output:
- An updated Excel file (modified in place).
- A `gaps_report.csv` file in the specified output directory.

## Development Tasks

This project uses `invoke` for task management, defined in `tasks.py`. After installing development dependencies (`pip install .[dev]`), you can use the following commands from the project root:

-   **Run the application:**
    ```bash
    python tasks.py run
    ```
-   **Run tests:**
    ```bash
    python tasks.py test
    ```
-   **Run linter (pyright):**
    ```bash
    python tasks.py lint
    ```
-   **Format code (black):**
    ```bash
    python tasks.py format
    ```
-   **Clean log files:**
    ```bash
    python tasks.py clean-logs
    ```
-   **Setup logs directory:**
    ```bash
    python tasks.py setup-logs
    ```
-   **Dump audit log:**
    ```bash
    python tasks.py dump-log
    ```
    Or, if the package is installed, you can also use:
    ```bash
    dump-coi-log
    ```
For a list of all available tasks, you can often run `python tasks.py --list`.
