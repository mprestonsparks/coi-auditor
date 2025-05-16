# COI Auditor Test Harness

This directory contains the test corpus and evaluation scripts for the `coi-auditor` project.

## 1. Test Corpus Structure

The test corpus is designed to store PDF COI documents and their corresponding ground truth annotations. The structure is as follows:

```
test_harness/
├── test_corpus/
│   ├── pdfs/                 # Directory for raw PDF files
│   │   ├── example_acord_standard.pdf
│   │   ├── example_multicolumn.pdf
│   │   └── ...
│   └── annotations/          # Directory for ground truth JSON annotations
│       ├── example_acord_standard.json
│       ├── example_multicolumn.json
│       └── ...
├── evaluation_scripts/       # Python scripts for the evaluation harness
│   ├── evaluate.py           # Main script to run evaluations
│   ├── metrics_calculator.py # Module for calculating accuracy metrics
│   └── report_generator.py   # Module for generating evaluation reports
└── README.md                 # This file
```

**Categorization:**

PDFs can be categorized by naming convention or by placing them in subdirectories within `test_corpus/pdfs/` if a more granular organization is needed in the future (e.g., `test_corpus/pdfs/acord_forms/`, `test_corpus/pdfs/problematic_ocr/`). For now, a flat structure within `pdfs/` is used, with descriptive filenames. The corresponding annotation files in `annotations/` should have the same base name as the PDF file but with a `.json` extension.

## 2. Ground Truth Annotation Format

Ground truth data for each PDF is stored in a JSON file. The format is designed to be clear, consistent, and easily parsable.

**Schema:**

Each JSON annotation file should adhere to the following structure:

```json
{
  "file_name": "example_acord_standard.pdf", // The original PDF filename
  "insured_name": "Accurate Builders Inc.",    // The primary name of the insured/subcontractor
  "alternate_insured_names": [                // Optional: List of other known names for matching
    "Accurate Builders",
    "Accurate Bldrs Inc"
  ],
  "insurance_policies": [
    {
      "policy_type": "General Liability",       // Standardized insurance type name
      "effective_date": "YYYY-MM-DD",         // Policy effective date
      "expiration_date": "YYYY-MM-DD",        // Policy expiration date
      "limit_amount": "1,000,000",            // Optional: Policy limit
      "carrier_name": "Example Insurance Co."   // Optional: Name of the insurance carrier
    },
    {
      "policy_type": "Automobile Liability",
      "effective_date": "YYYY-MM-DD",
      "expiration_date": "YYYY-MM-DD"
    },
    {
      "policy_type": "Workers Compensation", // Note: "Workers' Compensation" or "Workers Comp" might also be used, standardization is key
      "effective_date": "YYYY-MM-DD",
      "expiration_date": "YYYY-MM-DD"
    }
    // ... other policies
  ],
  "document_metadata": {                      // Optional: For additional document-level info
    "certificate_date": "YYYY-MM-DD",         // Date the certificate was issued
    "producer_name": "Reliable Insurance Agency",
    "holder_name": "Project Owner LLC"
  },
  "notes": "Optional notes about this specific COI, e.g., known OCR issues, specific layout quirks."
}
```

**Key Fields:**

*   `file_name`: (String, Required) The exact filename of the PDF document this annotation corresponds to.
*   `insured_name`: (String, Required) The primary name of the insured party as it appears on the COI, used for matching.
*   `alternate_insured_names`: (Array of Strings, Optional) A list of variations of the insured's name that might be encountered.
*   `insurance_policies`: (Array of Objects, Required) A list containing details for each insurance policy.
    *   `policy_type`: (String, Required) The type of insurance (e.g., "General Liability", "Workers Compensation", "Automobile Liability", "Umbrella Liability"). It's crucial to use a consistent set of names for policy types.
    *   `effective_date`: (String, Required) The policy's effective date in `YYYY-MM-DD` format.
    *   `expiration_date`: (String, Required) The policy's expiration date in `YYYY-MM-DD` format.
    *   `limit_amount`: (String, Optional) The coverage limit for the policy.
    *   `carrier_name`: (String, Optional) The name of the insurance carrier.
*   `document_metadata`: (Object, Optional) Contains additional metadata about the COI document itself.
    *   `certificate_date`: (String, Optional) The date the COI was issued, in `YYYY-MM-DD` format.
    *   `producer_name`: (String, Optional) The name of the insurance producer/agency.
    *   `holder_name`: (String, Optional) The name of the certificate holder.
*   `notes`: (String, Optional) Any relevant notes about the document, such as OCR quality, layout peculiarities, or specific challenges it presents.

**Consistency:**

*   **Date Format:** All dates MUST be in `YYYY-MM-DD` format.
*   **Policy Types:** A predefined, consistent list of `policy_type` names should be used across all annotations to ensure accurate aggregation of metrics. (This list should be maintained and documented separately if it grows complex).

## 3. Evaluation Harness Scripts

The evaluation harness consists of the following Python scripts located in the `test_harness/evaluation_scripts/` directory:

*   **`evaluate.py`**: The main script to orchestrate the evaluation process. It iterates through PDFs in the corpus, calls the COI parser, compares results with ground truth annotations, and uses other modules to calculate and report metrics.
*   **`metrics_calculator.py`**: Contains functions for detailed comparison between extracted data and ground truth. It calculates metrics such as precision, recall, and F1-score for date extraction, policy type identification, and insured name matching.
*   **`report_generator.py`**: Responsible for generating various output reports from the evaluation results, including text summaries, CSV files for detailed analysis, and JSON dumps of the full results.

These scripts are designed to be run from the root of the `coi-auditor` project.

## 4. Running the Evaluation

To run the evaluation harness:

1.  **Ensure your environment is set up:**
    *   The `coi-auditor` project and its dependencies should be installed.
    *   The Python interpreter used should have access to the `src.coi_auditor` package.

2.  **Prepare the Test Corpus:**
    *   Place your test PDF files in the `test_harness/test_corpus/pdfs/` directory.
    *   Create corresponding ground truth JSON annotation files in the `test_harness/test_corpus/annotations/` directory. Ensure the base filename of the annotation matches the PDF filename (e.g., `my_coi.pdf` and `my_coi.json`). Refer to Section 2 for the annotation format.

3.  **Execute the Evaluation Script:**
    Navigate to the root directory of the `coi-auditor` project in your terminal and run the `evaluate.py` script.

    ```bash
    python test_harness/evaluation_scripts/evaluate.py
    ```

    You can also specify alternative directories for the corpus and reports:

    ```bash
    python test_harness/evaluation_scripts/evaluate.py --corpus_dir path/to/your/corpus --reports_dir path/to/your/reports
    ```

    *   `--corpus_dir`: Path to the test corpus directory. Defaults to `test_harness/test_corpus/`.
    *   `--reports_dir`: Path to the directory where evaluation reports will be saved. Defaults to `test_harness/reports/`. This directory will be created if it doesn't exist.

4.  **Review the Output:**
    *   The script will print a summary of the evaluation to the console.
    *   Detailed reports (text summary, CSV, JSON) will be saved in the specified reports directory (default: `test_harness/reports/`).

**Example Placeholder Corpus:**

This harness includes a small placeholder corpus:
*   `test_harness/test_corpus/pdfs/FernandoHernandez_2024-09-19.pdf`
*   `test_harness/test_corpus/annotations/FernandoHernandez_2024-09-19.json`
*   `test_harness/test_corpus/pdfs/S&G Siding and Gutters_2023-10-18.pdf`
*   `test_harness/test_corpus/annotations/S&G Siding and Gutters_2023-10-18.json`

This allows for immediate testing of the harness functionality. The `parse_coi_pdf` function within `evaluate.py` currently uses a placeholder; for actual evaluation, it needs to correctly call the main `coi-auditor` parsing logic.