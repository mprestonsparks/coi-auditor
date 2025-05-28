# Certificate of Insurance (COI) Audit Automation

## 1. Purpose & Business Context
We need to verify that every subcontractor paid between **5/1/2024** and **5/1/2025** maintained uninterrupted General Liability (GL) and Workers’ Compensation (WC) coverage.  
Manual audit is error-prone and time-consuming; this script will:

- Read a master Excel list of subcontractor payments  
- Find and parse every COI PDF for each subcontractor  
- Extract and aggregate policy “From”/“To” dates across renewals  
- Flag any coverage gaps relative to the audit window  
- Write results back into the Excel and produce a consolidated CSV report  

## 2. Audit Window
- **Start:** 2024-05-01  
- **End:**   2025-05-01  

Any policy that begins _after_ the start date or ends _before_ the end date constitutes a gap.

## 3. Inputs

1. **Excel Workbook**  
   - **Path:** configured via `.env` (e.g.  
     `EXCEL_PATH=C:/…/Subcontractor-Payments.xlsx`)  
   - **Sheet:** `SUMMARY`
   - **Key columns:**  
     - **Name** (column B)  
     - **GL Policy Coverage Dates → From/To**  
     - **WC Policy Coverage Dates → From/To**

2. **COI PDFs Folder**  
   - Configured via `.env` (e.g.  
     `PDF_DIR=C:/…/Subcontractor COIs`)  
   - Filenames:  
     - Main format: `Some-Name_YYYY-MM-DD.pdf`  
     - Some split GL/WC docs: `Some-Name_GL_YYYY-MM-DD.pdf` or `Some-Name_WC_YYYY-MM-DD.pdf`

## 4. Outputs

1. **Excel Updates**  
   - Populate each row’s **GL From**, **GL To**, **WC From**, **WC To**  
   - Append two new columns: **GL Gap**, **WC Gap** (describing any gap or missing info)

2. **CSV Report**  
   - `gaps_report.csv` listing every contractor/policy with  
     - missing PDF  
     - missing parsed dates  
     - coverage gaps (e.g. “begins 2024-06-01 > audit start”)

## 5. High-Level Workflow

1. **Load Configuration**  
   Read paths, sheet name, audit window from `.env`.

2. **Open Excel & Identify Columns**  
   - Locate header row by finding “Name”  
   - Identify the merged headings for GL and WC, each spanning two columns (From/To)  
   - Create two more columns at the end for gap flags.

3. **Normalize & Match Names to PDFs**  
   - Strip each subcontractor name and PDF filename to a lowercase letters-only string.  
   - Select **all** PDFs whose normalized stem contains the normalized contractor name.

4. **Extract Dates from Each PDF**  
   - Use `pdfplumber` to pull raw text from every page.  
   - For **General Liability**, scan for keywords (`"general liability"`, `"GL policy"`, etc.), then grab the first two date-strings that follow.  
   - Repeat for **Workers’ Compensation**.

5. **Aggregate Across Renewals**  
   - For each subcontractor:  
     - **GL From:** earliest “effective” date among all GL matches  
     - **GL To:**   latest “expiration” date among all GL matches  
     - **WC From:** earliest WC date  
     - **WC To:**   latest WC date

6. **Detect Coverage Gaps**  
   - If **From** > audit start or **To** < audit end, mark a gap.  
   - If no PDFs or no parsable dates, flag as missing.

7. **Write Results**  
   - Update the Excel sheet in-place.  
   - Save a `gaps_report.csv` for follow-up.

## 6. Implementation Notes for Cascade AI

- **Language:** Python 3.x  
- **Main libraries:**  
  - `openpyxl` for Excel I/O  
  - `pdfplumber` for PDF text extraction  
  - `python-dotenv` for config  
- **File organization:**  
  - Single entry script (`audit_coi.py`) or split into modules (`config.py`, `excel_io.py`, `pdf_io.py`, `main.py`)  
  - `.env` in root for all paths and audit dates  
- **Error handling:**  
  - Robustly handle missing or unparsable PDFs  
  - Log any failures to the CSV and continue processing  
- **Extensibility hooks:**  
  - A future email-automation module could read the CSV and send standardized requests to insurance agents.  

---

> **Direct Cascade prompt:**  
> “Using the context above, generate a fully documented, PEP8-compliant Python program that automates the COI audit as described, including clear function decomposition, inline comments, and robust error handling. Ensure the program reads from `.env`, writes back into Excel, and produces a `gaps_report.csv`.”
