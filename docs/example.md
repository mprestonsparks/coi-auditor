Below is a single‐file Python script, `audit_coi.py`, which implements the entire COI-audit workflow you described. It:

1. Loads configuration (paths, worksheet name, audit period) from a `.env` file  
2. Opens your Excel workbook and locates the four policy-date columns  
3. Normalizes each subcontractor’s name and matches it against **all** PDFs in your COI folder  
4. For each PDF, extracts its GL and WC “effective” and “expiration” dates via simple text scanning  
5. Aggregates across multiple PDFs per subcontractor (earliest “From”, latest “To”)  
6. Detects any coverage gaps relative to your audit window (5/1/24–5/1/25)  
7. Writes back into Excel (two new “GL Gap”/“WC Gap” columns) **and** emits a `gaps_report.csv`

---

### Setup

1. **Install dependencies**  
   ```bash
   pip install openpyxl pdfplumber python-dotenv
   ```

2. **Create a `.env`** (in the same folder as `audit_coi.py`) with:
   ```ini
   EXCEL_PATH=C:/Users/Butle/Documents/Scott/SBH/Insurance/Insurance Audits/2025 Audits/Subcontractor-Payments.xlsx
   PDF_DIR=C:/Users/Butle/Documents/Scott/SBH/Insurance/Insurance Audits/2025 Audits/Subcontractor COIs
   SHEET_NAME=SUMMARY (with Policy Dates)
   AUDIT_START=2024-05-01
   AUDIT_END=2025-05-01
   ```

3. **Run**  
   ```bash
   python audit_coi.py
   ```

---

```python
# audit_coi.py

import os
import re
import csv
from pathlib import Path
from datetime import datetime, date
from collections import defaultdict

import pdfplumber
from openpyxl import load_workbook
from dotenv import load_dotenv

# ------------------------------------------------------------------------------
# 1) Configuration & Constants
# ------------------------------------------------------------------------------
load_dotenv()  # picks up .env in cwd

EXCEL_PATH = os.getenv("EXCEL_PATH")
PDF_DIR    = os.getenv("PDF_DIR")
SHEET_NAME = os.getenv("SHEET_NAME", "SUMMARY (with Policy Dates)")

# audit window
AUDIT_START = datetime.fromisoformat(os.getenv("AUDIT_START")).date()
AUDIT_END   = datetime.fromisoformat(os.getenv("AUDIT_END")).date()

# regex to find dates like 5/1/2024 or 05/01/24
DATE_RE = re.compile(r"(\d{1,2}/\d{1,2}/\d{2,4})")

# section keywords for robust matching
GL_KEYWORDS = ["general liability", "gl policy", "gl coverage"]
WC_KEYWORDS = ["workers compensation", "workers’ compensation", "wc policy", "wc coverage"]


# ------------------------------------------------------------------------------
# 2) Utility Functions
# ------------------------------------------------------------------------------

def normalize(s: str) -> str:
    """
    Lowercase + strip out everything except a–z, so we can match
    contractor names to PDF filenames even if punctuation differs.
    """
    return re.sub(r"[^a-z]", "", s.lower())


def parse_date(raw: str) -> date:
    """
    Given 'MM/DD/YYYY' or 'M/D/YY', returns a datetime.date.
    """
    parts = raw.split("/")
    year = parts[2]
    fmt = "%m/%d/%Y" if len(year) == 4 else "%m/%d/%y"
    return datetime.strptime(raw, fmt).date()


def extract_policy_dates(text: str, keywords: list[str]) -> tuple[date | None, date | None]:
    """
    Scan `text` for the first occurrence of any keyword in `keywords`,
    then take the first two dates found immediately afterward.
    Returns (from_date, to_date) or (None, None).
    """
    lower = text.lower()
    for kw in keywords:
        idx = lower.find(kw)
        if idx >= 0:
            snippet = text[idx : idx + 500]  # window after keyword
            found = DATE_RE.findall(snippet)
            if len(found) >= 2:
                return parse_date(found[0]), parse_date(found[1])
    return None, None


# ------------------------------------------------------------------------------
# 3) PDF → Date Extraction
# ------------------------------------------------------------------------------

def extract_all_dates_for_pdf(pdf_path: Path) -> dict[str, tuple[date|None, date|None]]:
    """
    Opens a PDF and returns {"GL": (from, to), "WC": (from, to)}.
    If a section isn’t found, its value will be (None, None).
    """
    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf)
    gl_from, gl_to = extract_policy_dates(full_text, GL_KEYWORDS)
    wc_from, wc_to = extract_policy_dates(full_text, WC_KEYWORDS)
    return {"GL": (gl_from, gl_to), "WC": (wc_from, wc_to)}


# ------------------------------------------------------------------------------
# 4) Main Processing
# ------------------------------------------------------------------------------

def main():
    # --- load workbook & worksheet
    wb = load_workbook(EXCEL_PATH)
    ws = wb[SHEET_NAME]

    # --- locate header rows & columns
    # find the row which has "Name" in it
    header_row = next(
        cell.row
        for row in ws.iter_rows(min_row=1, max_row=20)
        for cell in row
        if cell.value == "Name"
    )
    # the policy group headings just above
    group_row = header_row - 1

    # find the start column of each merged heading
    gl_group_col = next(cell.column for cell in ws[group_row] if cell.value == "GL Policy Coverage Dates")
    wc_group_col = next(cell.column for cell in ws[group_row] if cell.value == "WC Policy Coverage Dates")

    # policy date columns
    gl_from_col = gl_group_col
    gl_to_col   = gl_group_col + 1
    wc_from_col = wc_group_col
    wc_to_col   = wc_group_col + 1

    # prepare new "Gap" columns at end
    end_col = ws.max_column + 1
    gl_gap_col = end_col
    wc_gap_col = end_col + 1
    ws.cell(row=header_row, column=gl_gap_col, value="GL Gap")
    ws.cell(row=header_row, column=wc_gap_col, value="WC Gap")

    # cache PDF list once
    pdf_paths = list(Path(PDF_DIR).glob("*.pdf"))

    # for CSV report
    gaps_report = []

    # iterate each subcontractor
    for row in range(header_row + 1, ws.max_row + 1):
        name_cell = ws.cell(row=row, column=ws.cell(row=header_row, column=1).column + 1)  # find 'Name' col
        contractor = name_cell.value
        if not contractor:
            continue

        norm = normalize(contractor)

        # match all PDFs whose filename contains this normalized name
        matches = [
            p for p in pdf_paths
            if norm in normalize(p.stem)
        ]

        # if none found → record gap & continue
        if not matches:
            ws.cell(row=row, column=gl_gap_col, value="Missing ALL PDFs")
            ws.cell(row=row, column=wc_gap_col, value="Missing ALL PDFs")
            gaps_report.append([contractor, "ALL", "no COI PDF found"])
            continue

        # collect all dates for GL and WC
        gl_dates = []
        wc_dates = []

        for p in matches:
            dates = extract_all_dates_for_pdf(p)
            if dates["GL"][0]:
                gl_dates.append(dates["GL"])
            if dates["WC"][0]:
                wc_dates.append(dates["WC"])

        # find earliest-from & latest-to for each policy
        def aggregate(lst: list[tuple[date, date]]):
            if not lst:
                return None, None
            starts, ends = zip(*lst)
            return min(starts), max(ends)

        gl_from, gl_to = aggregate(gl_dates)
        wc_from, wc_to = aggregate(wc_dates)

        # write back into the sheet
        if gl_from: ws.cell(row=row, column=gl_from_col, value=gl_from)
        if gl_to:   ws.cell(row=row, column=gl_to_col,   value=gl_to)
        if wc_from: ws.cell(row=row, column=wc_from_col, value=wc_from)
        if wc_to:   ws.cell(row=row, column=wc_to_col,   value=wc_to)

        # check for gaps relative to audit window
        def check_gap(start: date | None, end: date | None, policy: str):
            if not start or not end:
                gaps_report.append([contractor, policy, "missing coverage dates"])
                return "MISSING"
            issues = []
            if start > AUDIT_START:
                issues.append(f"begins {start.isoformat()}>audit start")
            if end < AUDIT_END:
                issues.append(f"ends {end.isoformat()}<audit end")
            if issues:
                gaps_report.append([contractor, policy, "; ".join(issues)])
                return "; ".join(issues)
            return ""

        gl_gap = check_gap(gl_from, gl_to, "GL")
        wc_gap = check_gap(wc_from, wc_to, "WC")

        ws.cell(row=row, column=gl_gap_col, value=gl_gap)
        ws.cell(row=row, column=wc_gap_col, value=wc_gap)

    # --- save Excel
    wb.save(EXCEL_PATH)

    # --- write CSV
    with open("gaps_report.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Contractor", "Policy", "Issue"])
        writer.writerows(gaps_report)

    print("✅ Done. Workbook updated and gaps_report.csv generated.")


if __name__ == "__main__":
    main()
```

---

## How it works

1. **Configuration**  
   We load all paths and your audit window (`AUDIT_START`/`AUDIT_END`) from environment variables so you can tweak them without editing code.

2. **Excel parsing**  
   - We locate the row that has **Name** to find your header row.  
   - One row above lives the merged headings **GL Policy Coverage Dates** and **WC Policy Coverage Dates**, each spanning two columns (From/To).  
   - We record those four column indices, then append two more at the far right for **GL Gap** and **WC Gap**.

3. **Name ↔ PDF matching**  
   - Both the subcontractor name and every PDF filename are “normalized” to a contiguous lowercase string of only letters (everything else stripped).  
   - We match if the contractor’s normalized string is contained in the PDF’s normalized stem.  
   - **All** matching PDFs are kept—this lets us handle mid-period renewals.

4. **PDF date extraction**  
   - We open each PDF in `pdfplumber`, concatenate all pages’ text, and look for the **General Liability** and **Workers’ Comp** sections by keyword.  
   - After finding a keyword, we take the first two date-strings found in the next 500 characters as the start/end.  

5. **Aggregation & gap detection**  
   - Across all GL-PDFs we take the **earliest** “From” and the **latest** “To”. Likewise for WC.  
   - We compare those to your audit window (5/1/24–5/1/25). If coverage began after 5/1/24 or ended before 5/1/25, we flag it.  
   - Missing PDFs or missing date parses are also flagged.

6. **Output**  
   - The four date columns in the Excel sheet are filled in.  
   - The two new “GL Gap” / “WC Gap” columns note any coverage issues.  
   - A separate `gaps_report.csv` lists every contractor/policy that had a gap or missing data, so the auditor can follow up immediately.

---

With this in place your auditors will see, at a glance, for each subcontractor:

- **Exact** GL & WC coverage spans  
- **Any** coverage gaps flagged both in-sheet and in the CSV for outreach  

Let me know if you’d like any tweaks (e.g. different gap wording, email-automation hooks, etc.).