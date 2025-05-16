# Research Task: Open Source Document Layout Analysis Alternatives

## Context

The `coi-auditor` project aims to process PDF documents to extract information, including data from tables. A current dependency on a Hugging Face model (`nielsr/dit-base-finetuned-publaynet`) for document layout analysis is causing test failures due to authentication requirements, which violates the project's core directive to use only free and open-source libraries and tools without external authentication.

The model is accessed within the test suite, specifically in [`dit_test.py`](dit_test.py). Its primary function appears to be identifying structural elements within PDF page images, likely for downstream tasks like table detection or text block extraction.

## Project Directive

Strict adherence to using only free and open-source libraries and tools. No dependencies requiring external accounts, API keys, or authentication services are permitted.

## Research Objective

Identify and evaluate alternative free and open-source Python libraries for document layout analysis that can replace the functionality currently provided by the Hugging Face model, while strictly adhering to the project's directive.

## Research Questions

1.  What open-source Python libraries are available for document layout analysis (e.g., detecting text blocks, tables, figures) from images of document pages?
2.  Do these libraries require any form of external authentication, API keys, or accounts to use their core functionality or access pre-trained models?
3.  What are the licensing terms for these libraries and their associated pre-trained models (if any)? (Must be compatible with open source).
4.  How are these libraries typically installed and integrated into a Python project?
5.  What are the key features and capabilities of the most promising alternatives, particularly regarding table detection and layout parsing?
6.  Can these libraries process images (e.g., PNG, JPEG) derived from PDF pages?

## Expected Output Format

The research findings should be documented clearly in markdown format, suitable for direct inclusion or reference in project documentation. For each potential alternative library, please provide the following information:

### Library Name

*   **Description:** A brief overview of the library's purpose and capabilities.
*   **Licensing:** Explicitly state the license (e.g., MIT, Apache 2.0, GPL).
*   **Authentication Required?:** Clearly state YES or NO. If YES, explain what is required.
*   **Installation:** Provide the typical installation command (e.g., `pip install library_name`).
*   **Key Features (Relevant to COI Auditor):** List features relevant to document layout analysis, especially table detection and parsing.
*   **Code Example:** Provide a minimal Python code example demonstrating how to use the library for a basic layout analysis task (e.g., processing an image and identifying elements). Include necessary imports.
*   **Cross-references:** Use markdown links to relevant files in the `coi-auditor` project context where this functionality might be integrated or replace existing code (e.g., [`src/coi_auditor/pdf_parser.py`](src/coi_auditor/pdf_parser.py), [`dit_test.py`](dit_test.py)).
*   **Metadata/Tags:** Include relevant tags like `#document-layout-analysis`, `#open-source-research`, `#dependency-replacement`.

Please structure the response with clear headings and bullet points for readability. Ensure all claims about licensing and authentication are verified.