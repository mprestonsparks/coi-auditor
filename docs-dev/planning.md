# Planning
Date of Plan: 2025-05-15

## 1. Overall COI Audit Process Plan
(Based on "COI Audit Process: Step-by-Step Plan & Verification Suite" and "Conflict Analysis" items)

### 1.1. Configuration and Environment Setup
* Ensure `.env` is present and correct.
* All dependencies are installed.
* Logging is configured to file and console.

### 1.2. Excel File Loading
* Excel file exists and is accessible.
* Required columns are present (e.g., subcontractor name).
* Header row is correctly identified.

### 1.3. PDF Directory Scanning
* PDF directory exists and is accessible.
* All PDF files are listed and their filenames normalized (e.g., for consistent matching).

### 1.4. Fuzzy Matching: Excel Names to PDF Filenames
* For each subcontractor name in Excel:
    * Normalize the Excel name.
    * Compare the normalized Excel name to all normalized PDF filenames using fuzzy matching.
    * Assign similarity scores for each comparison.
    * Store and log all potential matches and their scores.
    * Select the best match above a configurable threshold.
    * Log the selected match and its score.
* If no match is found above the threshold, flag the subcontractor as "Missing PDF" or for manual review.
* Allow for review of matches and mismatches.
(This implements "Fuzzy Name Matching Implementation" and "Conflict Analysis Item 4". Supported by research from `research_prompts.md#Prompt-4` and `research.md#3.2`, related to REC-01)

### 1.5. Policy Type Detection
* For each matched PDF:
    * Detect if it pertains to General Liability (GL), Workers' Compensation (WC), or both (or other relevant types).
    * Ensure extraction proceeds only for the relevant policy type(s) specified for the audit.
(Implements "Conflict Analysis Item 5")

### 1.6. PDF Extraction (Date Extraction Focus)
* Open each matched PDF.
* Extract text content (possibly using OCR improvements from REC-08).
* For relevant policy types, search for effective and expiration dates using the enhanced parsing logic (see Section 2 below, covering REC-01 to REC-07).
* Store and log all extracted dates and any issues encountered.
(Implements "Conflict Analysis Item 6")

### 1.7. Aggregation and Gap Analysis
* Aggregate all extracted policy effective and expiration dates for each subcontractor.
* Determine insurance coverage gaps based on the specified audit period and the extracted dates.
* Record all results, identified gaps, and any issues encountered during aggregation.
(Implements "Conflict Analysis Item 7")

### 1.8. Output Results
* Update the original Excel file (or a copy) with extraction results, including identified gaps and missing PDF flags.
* Generate a separate gaps report (e.g., CSV format).
* Ensure all output files are saved to a designated location and are accessible.

### 1.9. Verification Suite and Execution
* **Verification Suite (Test Functions):**
    1.  `test_env_and_config()`
    2.  `test_excel_loading()`
    3.  `test_pdf_dir_scanning()`
    4.  `test_fuzzy_matching()`
    5.  `test_policy_type_detection()`
    6.  `test_pdf_extraction()` (will need to be updated as extraction logic evolves with RECs)
    7.  `test_aggregation_and_gap_analysis()`
    8.  `test_output_files()`
* **Execution Instructions:**
    * Implement each main audit process task and its corresponding test function in order.
    * After each task's implementation, run its test and verify correctness.
    * If successful, proceed to the next task.
    * If a test fails, debug and fix the task's implementation before continuing.
    * At the end of a full run, provide a summary of which steps passed or failed.

## 2. Plan for Enhancing PDF Date Extraction
(Based on "Analysis and Recommendations for Enhancing PDF Date Extraction in COI Auditor")

The overarching recommendations prioritize a strategic evolution of the primary parser by implementing adaptive header searches, layout-aware columnar processing, and comprehensive OCR error handling. A flexible framework for configurable layout strategies is also key.

### Prioritization of Enhancements:
(From "Analysis and Recommendations..." Section 2 / Response to Briefing Question 6.2)
* **Tier 1 (Highest Priority):** REC-01, REC-02
* **Tier 2 (Medium Priority):** REC-03, REC-04
* **Tier 3 (Lower Priority / Long-term Strategy):** REC-05, REC-06, REC-07, REC-08 (Note: Basic OCR pre-processing from REC-08 like deskewing can be high priority).

---
**Recommendation Details:**

### REC-01: Implement Enhanced Header Detection with Fuzzy Matching and Spatial Analysis
* **Description:** Improve identification of "POLICY EFF," "POLICY EXP," "POLICY NUMBER" using fuzzy string matching for OCR errors/variations and relative spatial positioning.
* **Rationale:** Foundational improvement; accurate header detection is critical. Addresses OCR errors in headers.
* **Affected Component(s):** `src/coi_auditor/pdf_parser.py` (header identification functions).
* **Expected Benefits/Impact:** Increased accuracy and robustness in identifying date column headers.
* **Cross-reference:** Supported by research from `research_prompts.md#Prompt-4-Fuzzy-Matching-Algorithms...`.
* **Priority:** High (Tier 1).

### REC-02: Develop Adaptive Header Search for Section-Specific Date Headers
* **Description:** If global "POLICY EFF/EXP" search fails for a section, attempt localized search near that section's header.
* **Rationale:** Addresses "per-section mini-tables" without a separate fallback system.
* **Affected Component(s):** `src/coi_auditor/pdf_parser.py` (extending `extract_dates_from_pdf()`).
* **Expected Benefits/Impact:** Successful date extraction from COIs with per-section date headers.
* **Priority:** High (Tier 1).

### REC-03: Implement Layout-Aware Columnar Processing Module
* **Description:** Develop a module for high-level page layout analysis (multi-column detection). Apply primary parsing logic iteratively to each detected column.
* **Rationale:** Addresses "two-column certificates." Reuses primary logic in a targeted manner.
* **Affected Component(s):** `src/coi_auditor/pdf_parser.py` (new sub-module for layout analysis, modifications to `extract_dates_from_pdf()`).
* **Detailed Plan (from "REC-03: Layout-Aware Columnar Processing - Path Forward Recommendation"):**
    * **Approach:** Hybrid (ML for Tables, Heuristics for Columns).
        * Leverages strengths: ML (TATR) for complex table detection (from `research.md#1`), heuristics for general page layout.
        * Allows incremental development and reduces initial ML overhead for general columns.
    * **Phase 1: Foundational Components**
        1.  **Robust Heuristic Page-Level Column Detection:** Develop sophisticated heuristic algorithm (e.g., improved whitespace analysis, text block bounding boxes) to identify primary columnar structure (1, 2, or 3 columns), outputting bounding boxes.
        2.  **ML-based Table Detection (Leverage TATR):** Integrate TATR model (from TASK-02 prototype, `src/coi_auditor/ml_column_detector_prototype.py`) for identifying "table" regions and their bounding boxes.
    * **Phase 2: Integration and Refinement**
        3.  **Layout Reconciliation Logic:** Combine outputs of heuristic page-column detector and ML table detector to create a definitive set of "processing regions" (full page columns or specific table areas). Handle overlaps (e.g., table spanning multiple page columns, table within a page column).
        4.  **Adapt Parsing Logic:** Modify parsing functions in `src/coi_auditor/pdf_parser.py` (e.g., `find_section_header_roi`, `find_column_rois`, `generate_date_candidates_in_roi`) to accept a "processing region" bounding box and operate within it. `extract_dates_from_pdf` will loop through these regions.
    * **Phase 3: Advanced Enhancements (Future Work, Post REC-03 Core)**
        5.  **ML for Table Structure Recognition:** Investigate models like `microsoft/table-transformer-structure-recognition` (if FOSS) to extract row/column details *within* tables detected by TATR.
        6.  **ML for Page-Level Column Detection (If Heuristics Insufficient):** Revisit a dedicated ML approach if robust heuristics are too difficult. Requires annotation effort for training/fine-tuning.
* **Expected Benefits/Impact:** Accurate date extraction from multi-column COIs.
* **Cross-reference:** Based on research on TATR in `research.md#1-Feasibility-of-ML-based-Column-and-Table-Detection`. Integration point: after page image preprocessing, before detailed word/text extraction.
* **Priority:** Medium (Tier 2).
* **Next Steps (Initiating REC-03):**
    1.  Begin development of robust heuristic page-level column detection (Phase 1.1).
    2.  Concurrently, start integrating TATR table detection prototype (Phase 1.2).
    3.  Plan data structures/interfaces for layout reconciliation logic (Phase 2.3).

### REC-04: Refine Vertical ROI for Wrapped Date Cells
* **Description:** Extend vertical search area downwards from the insurance type's main text line to catch wrapped date values.
* **Rationale:** Targeted refinement for "wrapped date cells" issue.
* **Affected Component(s):** `src/coi_auditor/pdf_parser.py` (logic for vertical search bounds).
* **Expected Benefits/Impact:** Improved recall for dates that wrap to a new line.
* **Priority:** Medium (Tier 2).

### REC-05: Establish a Framework for Configurable Layout Strategy Profiles
* **Description:** Design architecture for multiple "layout strategy" configurations. Each profile tunes parameters, heuristics, and selects/enables processing modules (e.g., adaptive header search, REC-02; columnar processing, REC-03) for the primary parser.
* **Rationale:** Robust, maintainable solution for COI layout diversity. Avoids monolithic parser.
* **Affected Component(s):** Core architecture of `coi_auditor.pdf_parser`, new configuration management.
* **Expected Benefits/Impact:** Greater flexibility and accuracy across diverse COI layouts; improved maintainability.
* **Priority:** Medium (Tier 3 - Framework dev after initial core improvements).

### REC-06: Integrate Named Entity Recognition (NER) for Date Normalization and Validation
* **Description:** Post-extraction, use a date-focused NER model/tool to parse, normalize (to YYYY-MM-DD), and validate date strings.
* **Rationale:** Handles diverse date formats more robustly than regex alone.
* **Affected Component(s):** `src/coi_auditor/pdf_parser.py` (post-processing).
* **Expected Benefits/Impact:** More accurate parsing and normalization of diverse date formats.
* **Cross-reference:** See TASK-03 plan below.
* **Priority:** Medium-Low (Tier 3 - Implement after core parsing logic is stabilized).

### REC-07: Investigate Machine Learning-Based Layout Segmentation for Complex COIs
* **Description:** For highly complex/non-standard layouts where heuristic section ID or REC-03 is insufficient, research/prototype ML models (e.g., LayoutLM) for document layout segmentation.
* **Rationale:** ML can identify logical regions with greater robustness to variations.
* **Affected Component(s):** Potential new ML module integrated into `pdf_parser.py`, possibly as a REC-05 profile.
* **Expected Benefits/Impact:** Improved processing of very challenging COIs.
* **Cross-reference:** Connects to potential future work for REC-03 Phase 3 and `research_prompts.md#Prompt-2`.
* **Priority:** Low (Tier 3 - Research/Prototyping phase first).

### REC-08: Establish Comprehensive OCR Pre-processing and Post-processing Pipeline
* **Description:** Implement robust OCR enhancement: image pre-processing (deskewing, denoising, binarization) and text post-processing (spell checking, contextual validation).
* **Rationale:** Foundational; improved OCR accuracy benefits all downstream logic.
* **Affected Component(s):** OCR processing stage, upstream of `pdf_parser.py`.
* **Expected Benefits/Impact:** Significantly improved OCR accuracy, reducing overall parsing errors.
* **Cross-reference:** See `research_prompts.md#Prompt-3-Best-Practices-for-OCR...` and `research.md#3.1-OCR-Improvement-Strategies`.
* **Priority:** High for pre-processing basics (Tier 1); Medium for advanced post-processing (Tier 3).

---
## 3. Proposed New Development Tasks

### TASK-01: Develop a COI PDF Test Corpus and Evaluation Harness
* **Objective:** Create a diverse, representative dataset of COI PDFs (various layouts, OCR quality examples) and an automated framework for evaluating date extraction accuracy and parser performance.
* **Key Deliverables/Outcomes:**
    1.  Annotated COI PDF dataset with ground truth for policy dates.
    2.  Evaluation scripts to run `coi-auditor` on the corpus and compare against ground truth.
    3.  Standardized metrics (precision, recall, F1-score for date extraction).
    4.  Baseline accuracy metrics and process for tracking improvements.
* **Relevant Recommendation ID(s):** Supports all recommendations (REC-01 through REC-08).

### TASK-02: Research and Prototype ML-based Column Detection for COIs (Status Update)
* **Original Objective:** Investigate and evaluate feasibility of ML for identifying columnar structures.
* **Summary of Findings:**
    * LayoutLMv3: Rejected (license, setup issues).
    * DETR: Tested, output too generic.
    * Table-Transformer (TATR): Feasible and effective for "table" detection. Does not directly identify general page-level columns.
    * (Full details in `research.md#1-Feasibility-of-ML-based-Column-and-Table-Detection`)
* **Current Status of Prototype Efforts (from "ML-Based Column Detection Prototype: Status and Research Brief"):**
    * The "Feasibility Report" in `research.md` represents the conclusion of the main research phase of TASK-02, with TATR identified as the key model for table detection.
    * The earlier "Status and Research Brief" detailed experimentation steps:
        * Initial attempts with LayoutLMv3 faced persistent import errors (see `research_prompts.md#Prompt-1`).
        * A pivot to DETR (`facebook/detr-resnet-50`) was made. The last known blocker was a missing `timm` library dependency.
    * **Resolution:** The findings in the Feasibility Report (TATR for tables, DETR not ideal) supersede the DETR-specific next steps from the "Status Brief." The `timm` library issue for DETR is likely resolved or irrelevant if DETR is not pursued for column detection as per REC-03's hybrid plan.
* **TASK-02 Conclusion:** The research and prototyping for initial feasibility are largely complete. The path forward for column/table detection is detailed in REC-03, leveraging TATR for tables.

### TASK-03: Investigate and Benchmark Date NER Models and Libraries
* **Objective:** Identify, evaluate, and benchmark off-the-shelf or fine-tunable NER models/libraries for accurately extracting and normalizing date formats from COI text snippets.
* **Key Deliverables/Outcomes:**
    1.  Comparative report on suitable date NER models/libraries (e.g., spaCy, Spark NLP, AllenNLP, Hugging Face Transformers models).
    2.  Performance benchmarks on a curated COI date string dataset.
    3.  Recommendation for the most suitable NER solution for REC-06.
* **Relevant Recommendation ID(s):** REC-06 (Integrate NER for Date Normalization and Validation).

## 4. Other Planning Considerations
(From "Analysis and Recommendations..." Section 5)

* **Human-in-the-Loop (HITL) Strategy:** Consider for future implementation for edge cases, model training data generation, and identifying failure patterns.
* **Performance Monitoring and Continuous Feedback Loops:** Implement robust logging of extraction rates, confidence scores, and processing times. Establish a user feedback mechanism for error reporting.
* **Data Augmentation for ML Models:** Consider if pursuing REC-07 or fine-tuning for REC-03 Phase 3, if large annotated COI datasets are scarce.
* **Ethical Considerations and Bias in AI:** Maintain awareness of potential biases in pre-trained models, though a lesser concern for date extraction compared to broader semantic tasks. Adhere to responsible AI practices.

## Source Documents Referenced:
* Internal document: "Analysis and Recommendations for Enhancing PDF Date Extraction in COI Auditor"
* Internal document: "REC-03: Layout-Aware Columnar Processing - Path Forward Recommendation"
* Internal document: "ML-Based Column Detection Prototype: Status and Research Brief" (for historical context on TASK-02)