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
    ```bash
    pip install -r requirements.txt
    ```
2.  **Configure paths and dates:**
    - Create a `.env` file in the project root (copy `.env.example` if provided).
    - Update the paths (`EXCEL_FILE_PATH`, `PDF_DIRECTORY_PATH`, `OUTPUT_DIRECTORY_PATH`) and audit dates (`AUDIT_START_DATE`, `AUDIT_END_DATE`).
3.  **Prepare input files:**
    - Ensure the Subcontractor Excel file exists at the specified path.
    - Ensure the COI PDFs are located in the specified directory, following naming conventions if applicable.

## Usage

```bash
python -m coi_auditor.main
```

The script will process the files and output:
- An updated Excel file (modified in place).
- A `gaps_report.csv` file in the specified output directory.
