# Research
Date of Analysis: 2025-05-15

## 1. Feasibility of ML-based Column and Table Detection for COIs (TASK-02 Summary)

This section summarizes the findings from **TASK-02: Research and Prototype ML-based Column Detection for COIs**. The primary output of this task is the "Feasibility Report: ML-based Column Detection for COIs."

### 1.1. Objective of TASK-02
The objective was to prototype and evaluate the feasibility of using machine learning (ML) techniques for detecting columnar layouts, particularly table structures, within Certificate of Insurance (COI) documents.

### 1.2. Models Investigated
Several models were considered and evaluated:

* **LayoutLMv3:** Initially considered for its strong performance in document layout understanding.
    * **Outcome:** Rejected due to its CC-BY-NC-SA 4.0 license (not FOSS-compliant for the project's purposes) and persistent import/setup issues encountered during initial setup (detailed in `research_prompts.md#Prompt-1`).
* **DETR (`facebook/detr-resnet-50`):** Tested as a FOSS alternative.
    * **Outcome:** While it successfully performed object detection, its output was too generic for detailed layout analysis (e.g., detecting "book" or "remote"), and not specific enough for identifying table or column structures.
* **Table-Transformer (TATR - `microsoft/table-transformer-detection`):**
    * **Outcome:** Chosen as the final model for the prototype. It is FOSS-compliant (MIT license) and specifically designed for table detection. TATR successfully identified "table" structures in test COI documents with high confidence scores.

### 1.3. Data Assessment for ML Prototyping
* **COI Test Corpus:** The existing corpus at `test_harness/test_corpus/pdfs/` was used for inference.
* **Annotation Needs:**
    * For the inference-based prototype using pre-trained TATR, no new annotations were strictly required.
    * Future work involving fine-tuning for improved performance or quantitative evaluation would necessitate a dedicated annotated dataset (bounding boxes for tables, columns, etc.).

### 1.4. Prototype Description (`ml_column_detector_prototype.py`)
The prototype script using TATR:
* Converts PDF pages to images (PNG, 300 DPI).
* Performs object detection using the pre-trained TATR model.
* Outputs JSON files with detected objects (label, score, bounding box) and PNG images with visual overlays.

### 1.5. Initial Evaluation & Performance Insights (TATR)
* TATR successfully identified "table" structures in test COIs.
* The pre-trained TATR model detects "tables" and related structures but does not directly output "column" labels for general page-level columnar layouts outside of explicit table structures.
* Detected table boundaries are a positive step for document structure understanding and can serve as a basis for inferring internal column structures.

### 1.6. Feasibility Recommendation for REC-03 (ML-led Column Detection)
* **Table Detection:** An ML-led approach (e.g., TATR) is **feasible for detecting table structures**. This is likely more robust than heuristics for complex tables.
* **Direct Page-Level Column Detection:** Not yet demonstrated with pre-trained TATR. Heuristics might be competitive or preferable for this specific sub-task currently.
* **Further TATR Evaluation:** Recommended on a more diverse COI set.
* **Post-processing of TATR Output:** Develop logic to analyze TATR-detected "table" objects to infer internal columns.
* **Explore TATR for Structure Recognition:** Investigate related models like `microsoft/table-transformer-structure-recognition` (if FOSS compliant) for more granular table details (see `planning.md#REC-03` Phase 3).
* **Fine-tuning:** Could teach TATR or similar models to explicitly identify page-level columns with an annotated dataset.
* **Alternative FOSS Models:** Continue monitoring for new FOSS models for document layout analysis.

### 1.7. Conclusion of TASK-02
ML models (specifically TATR) are capable of detecting table structures in COIs. This is promising for REC-03. Direct page-level column detection requires further work (post-processing, fine-tuning, or other models). The "REC-03: Layout-Aware Columnar Processing - Path Forward Recommendation" (see `planning.md#REC-03`) builds upon these findings.

## 2. Analysis of PDF Date Extraction Challenges in COI Auditor

This section draws from the "Analysis and Recommendations for Enhancing PDF Date Extraction in COI Auditor" document.

### 2.1. Background: Current Primary Date Extraction Logic
The current logic in `src/coi_auditor/pdf_parser.py` primarily:
1.  Identifies page-level "POLICY EFF" and "POLICY EXP" column headers.
2.  Identifies the vertical span of specific insurance sections (e.g., "COMMERCIAL GENERAL LIABILITY").
3.  Searches for date values within the section's span, aligned with the page-level date headers.
This is effective for common ACORD-25 layouts with global date headers.

### 2.2. Identified Challenges with Layout Variations
The primary logic can fail with layouts such as:
1.  **Per-section mini-tables:** "POLICY EFF/EXP" repeated under each coverage.
2.  **Two-column certificates:** Different insurance types in separate columns with their own date columns.
3.  **Three-column header issues:** OCR dropping "POLICY NUMBER" can shift date x-offsets.
4.  **Wrapped date cells:** Long policy numbers pushing dates to new lines.
(Source: `research.md` "Key Context from Previous Discussions" A3.1; Briefing Document Section 2.2)

### 2.3. Critique of the "Legacy Fallback Parser" Concept
The idea of a separate "legacy fallback parser" was critiqued due to:
* Increased complexity and maintenance overhead.
* Difficulty in defining reliable triggers for fallback.
* Risk of compounding errors.
* Potentially inefficient development effort compared to enhancing the primary parser.
* Effort better invested in making the primary parser more robust.
(Source: `planning.md` "Briefing Document" Section 3)
The conclusion is that enhancing the primary parser is preferable (see `planning.md` Section 2, Response to Briefing Question 6.6).

### 2.4. Evaluation of Proposed Enhancements to the Primary Parser
The following alternatives to a fallback parser were analyzed (details in Table 1 of the "Analysis and Recommendations..." document, summarized here):

* **Adaptive Header Search:** (Briefing Doc 4.1) Localized search for "POLICY EFF/EXP" if global fails.
    * *Pros:* Targets "per-section mini-tables"; reuses primary components.
    * *Cons:* Defining search vicinity; potential performance impact.
* **Layout-Aware Columnar Processing:** (Briefing Doc 4.2) Pre-processing for multi-column detection; iterative application of primary logic.
    * *Pros:* Handles "two-column certificates"; reuses primary logic.
    * *Cons:* Accuracy dependent on column segmentation. (See `planning.md#REC-03` for detailed plan).
* **Enhanced Robustness for Header Detection:** (Briefing Doc 4.3) Fuzzy matching and spatial positioning for key headers.
    * *Pros:* Improves reliability; mitigates minor OCR errors.
    * *Cons:* Overly aggressive fuzzy matching risks false positives. (See `planning.md#REC-01` and `research_prompts.md#Prompt-4`).
* **Configurable Layout Strategies/Profiles:** (Briefing Doc 4.4) Multiple configurations for the primary parser.
    * *Pros:* Flexible; maintainable way to handle COI diversity.
    * *Cons:* Managing profile proliferation; reliable auto-matching. (See `planning.md#REC-05`).
* **Refined Vertical ROI for Wrapped Date Cells:** (Briefing Doc 4.5) Extend vertical search area downwards.
    * *Pros:* Simple fix for wrapped dates.
    * *Cons:* Might pick up unrelated data. (See `planning.md#REC-04`).

### 2.5. Analysis of Other Considered Techniques for Date Extraction
(Details in Table 2 of the "Analysis and Recommendations..." document, summarized here):

* **ML-based Layout Analysis (CNNs, Transformers like LayoutLM, Donut):** For logical region identification.
    * *Pros:* Robust to layout variations.
    * *Cons:* Requires annotated data; development effort. (Partially addressed by `planning.md#REC-07` and `research.md#1` for tables).
* **Graph Neural Networks (GNNs) for Document Structure:** For complex/distorted COIs.
    * *Pros:* Captures relational context; robust to distortions.
    * *Cons:* Cutting-edge; higher complexity; needs expertise.
* **Dedicated Named Entity Recognition (NER) for Dates:** (e.g., BERT-based, Spark NLP DateMatcher).
    * *Pros:* Handles diverse date formats.
    * *Cons:* Depends on good OCR and region identification. (See `planning.md#REC-06` and `planning.md#TASK-03`).
* **Advanced OCR Pre-processing & Post-processing:** Deskewing, denoising, binarization, error correction.
    * *Pros:* Reduces OCR errors, higher overall accuracy.
    * *Cons:* May need OCR engine internals; adds computation. (See `planning.md#REC-08` and `research.md#3.1`).
* **Template-Based Extraction for Known High-Volume Forms:** Explicit templates for specific ACORD versions.
    * *Pros:* High accuracy/speed for known layouts.
    * *Cons:* Not scalable to many variations; template maintenance. (Could be part of `planning.md#REC-05`).

### 2.6. Analysis of Strategies for Managing Layout Variations
(Details in Table 3 of the "Analysis and Recommendations..." document, summarized here):

* **Single, Highly Adaptive Primary Parser (Rule-Based/Heuristic):**
    * *Maintainability:* Low to Medium (can become complex).
    * *Scalability:* Medium.
    * *Robustness:* Medium.
* **Configurable Layout Strategy Profiles (Briefing Doc 4.4):**
    * *Maintainability:* Medium (modular profiles).
    * *Scalability:* Medium to High.
    * *Robustness:* High within a profile. (Recommended approach, see `planning.md#REC-05`).
* **Hybrid Approach (Rule-Based + ML Components):**
    * *Maintainability:* Medium to High (MLOps but can simplify rules).
    * *Scalability:* High.
    * *Robustness:* High. (Promising long-term strategy).
* **Purely ML-Driven Approach (End-to-End Models):**
    * *Maintainability:* Medium (requires ML expertise, MLOps).
    * *Scalability:* High (if model generalizes).
    * *Robustness:* Potentially Very High. (Future direction, high risk/effort now).

## 3. Supporting Technologies Research

### 3.1. OCR Improvement Strategies and Best Practices
Improving OCR quality is foundational. Key strategies include:
(Derived from Table 4 of "Analysis and Recommendations for Enhancing PDF Date Extraction in COI Auditor")

| Phase                        | Technique/Best Practice                                 | Description & Benefit                                                                    | Tools/Considerations                               |
|------------------------------|---------------------------------------------------------|------------------------------------------------------------------------------------------|----------------------------------------------------|
| **Image Acquisition** | High-Resolution Scanning                                | Min 300 DPI (pref 600 DPI) for more pixel data.                                          | Scanner settings.                                  |
|                              | Good Lighting & Focus                                   | Even lighting, no shadows/glare, flat document, in focus.                                | Physical environment, camera quality.              |
| **Pre-processing** | Deskewing                                               | Correct tilt/skew for better segmentation.                                               | OpenCV, Leptonica.                                 |
|                              | Denoising                                               | Remove noise/speckles interfering with recognition.                                      | Median filter, bilateral filter.                   |
|                              | Binarization                                            | Convert to B&W; adaptive thresholding often superior.                                    | Otsu's method, adaptive thresholding in OpenCV.    |
|                              | Removal of Background Patterns/Non-Textual Elements     | Eliminate patterns, watermarks, graphics.                                                | Image segmentation, filtering.                     |
| **Recognition (OCR Engine)** | Language Specification                                  | Set correct language.                                                                    | OCR engine parameters.                             |
|                              | Font Considerations                                     | Clear fonts (Arial, Times New Roman, 10-12pt+) yield better results.                     | Document creation guidelines.                      |
|                              | Page Segmentation Mode (PSM)                            | Choose appropriate PSM (e.g., single column, auto).                                      | Tesseract OCR parameters.                          |
| **Post-processing** | Spell Checking & Lexical Correction                     | Use dictionaries for common OCR misspellings, domain terms.                              | Spell checkers, custom dictionaries.               |
|                              | Contextual Validation                                   | Use language models/n-grams to correct errors (advanced).                                | NLP libraries.                                     |
|                              | Rule-Based Correction                                   | Fix systematic OCR errors (e.g., "P0LICY EFF").                                          | Custom scripts.                                    |
|                              | Confidence Scoring                                      | Use OCR confidence scores to flag low-confidence regions.                                | OCR engine API.                                    |
| **Evaluation** | Metrics (CER, WER)                                      | Regularly evaluate accuracy using Character/Word Error Rate.                             | Evaluation scripts, Levenshtein distance.          |
(See `research_prompts.md#Prompt-3` for ongoing research in this area and `planning.md#REC-08` for planned implementation).

### 3.2. Fuzzy Matching Techniques
Research into optimal fuzzy matching algorithms and parameter tuning is ongoing.
(See `research_prompts.md#Prompt-4` for research questions to support `planning.md#REC-01`).

## Source Documents Referenced:
* Internal document: "Feasibility Report: ML-based Column Detection for COIs" (content integrated herein)
* Internal document: "ML-Based Column Detection Prototype: Status and Research Brief" (content integrated herein and in `planning.md`/`research_prompts.md`)
* Internal document: "Briefing Document: Enhancing PDF Date Extraction in COI Auditor" (context for analysis)
* Internal document: "Analysis and Recommendations for Enhancing PDF Date Extraction in COI Auditor" (primary source for Section 2 and 3.1)