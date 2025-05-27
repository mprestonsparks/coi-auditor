import argparse
import json
import os
import sys
from datetime import datetime

# Add the project root to the Python path to allow importing coi_auditor
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

try:
    # Attempt to import the main date extraction function
    from src.coi_auditor.pdf_parser import extract_dates_from_pdf
except ImportError:
    print("Error: Could not import extract_dates_from_pdf from src.coi_auditor.pdf_parser.")
    print(f"Current sys.path: {sys.path}")
    # Define a placeholder if the import fails
    def extract_dates_from_pdf(pdf_path, indicator=None): # pragma: no cover
        print(f"Warning: Using placeholder extract_dates_from_pdf for {pdf_path}. Actual function not imported.")
        # This placeholder returns a structure similar to the actual function: (dates_dict, note_str)
        # However, this structure is NOT what calculate_overall_metrics expects for its `extracted_data` argument.
        # calculate_overall_metrics expects a dict with 'insured_name' and policy types as keys.
        # This highlights a mismatch that needs to be resolved for the harness to work.
        return ({"gl_effective": "2024-01-01", "gl_expiration": "2025-01-01"}, "Placeholder note")

# Import from metrics_calculator
try:
    from .metrics_calculator import calculate_overall_metrics, aggregate_corpus_metrics, normalize_policy_type
    from .report_generator import generate_text_summary, generate_csv_report, generate_json_report
except ImportError: # Fallback for direct execution if '.' fails
    from metrics_calculator import calculate_overall_metrics, aggregate_corpus_metrics, normalize_policy_type
    from report_generator import generate_text_summary, generate_csv_report, generate_json_report


def run_evaluation(corpus_dir, reports_output_dir):
    """
    Runs the evaluation process on the test corpus.
    """
    pdfs_dir = os.path.join(corpus_dir, "pdfs")
    annotations_dir = os.path.join(corpus_dir, "annotations")

    if not os.path.isdir(pdfs_dir): # pragma: no cover
        print(f"Error: PDFs directory not found at {pdfs_dir}")
        return
    if not os.path.isdir(annotations_dir): # pragma: no cover
        print(f"Error: Annotations directory not found at {annotations_dir}")
        return
    
    if not os.path.exists(reports_output_dir): # pragma: no cover
        os.makedirs(reports_output_dir)
        print(f"Created reports directory: {reports_output_dir}")

    results = []
    overall_stats = {
        "total_files": 0,
        "processed_files": 0,
        "failed_parsing": 0,
        "missing_annotations": 0,
        # More detailed stats will be added here
    }

    for pdf_filename in os.listdir(pdfs_dir):
        if not pdf_filename.lower().endswith(".pdf"):
            continue

        overall_stats["total_files"] += 1
        pdf_path = os.path.join(pdfs_dir, pdf_filename)
        annotation_filename = os.path.splitext(pdf_filename)[0] + ".json"
        annotation_path = os.path.join(annotations_dir, annotation_filename)

        if not os.path.exists(annotation_path):
            print(f"Warning: Annotation file not found for {pdf_filename}. Skipping.")
            overall_stats["missing_annotations"] += 1
            continue

        try:
            with open(annotation_path, 'r') as f:
                ground_truth_data = json.load(f)
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON for {annotation_filename}. Skipping.")
            continue
        except Exception as e:
            print(f"Error loading annotation {annotation_filename}: {e}. Skipping.")
            continue
            
        print(f"\nProcessing: {pdf_filename}")
        start_time = datetime.now()

        try:
            # Call the imported date extraction function.
            # Note: extract_dates_from_pdf returns a tuple: (dates_dict, note_string)
            # This is NOT the structure expected by calculate_overall_metrics.
            # calculate_overall_metrics expects a single dictionary containing insured_name
            # and policy types as keys, with their respective date dicts as values.
            # This is a major discrepancy that needs to be addressed for the evaluation to be meaningful.
            # For now, we'll call it and pass its result, but it will likely lead to errors
            # or incorrect metrics in calculate_overall_metrics.
            dates_dict, note_str = extract_dates_from_pdf(pdf_path) # indicator might be needed if logic changes
            
            # TODO: Bridge the gap between extract_dates_from_pdf output and calculate_overall_metrics input.
            # This might involve:
            # 1. Modifying extract_dates_from_pdf to also return insured_name and structure policy types.
            # 2. Creating an adapter function here to transform the output.
            # 3. Revising calculate_overall_metrics to accept the current output format (less likely).
            # For now, creating a placeholder structure for extracted_data based on dates_dict.
            extracted_data_for_metrics = {
                "insured_name": "NOT_EXTRACTED_BY_CURRENT_FUNCTION", # Insured name is not part of extract_dates_from_pdf output
                # Policy types need to be inferred or structured differently by pdf_parser
                # This is a simplified placeholder:
                "general_liability": {
                    "effective_date": dates_dict.get("gl_effective"),
                    "expiration_date": dates_dict.get("gl_expiration")
                },
                "workers_compensation": {
                    "effective_date": dates_dict.get("wc_effective"),
                    "expiration_date": dates_dict.get("wc_expiration")
                },
                # Add other policy types if extract_dates_from_pdf handles them
            }
            # Log the note from the parser
            if note_str:
                print(f"  Parser note for {pdf_filename}: {note_str}")

        except Exception as e:
            print(f"Error calling extract_dates_from_pdf for {pdf_filename}: {e}")
            overall_stats["failed_parsing"] += 1
            continue
        
        processing_time = (datetime.now() - start_time).total_seconds()
        print(f"Processing time: {processing_time:.2f} seconds")

        # Compare extracted data with ground truth
        individual_metrics = calculate_overall_metrics(extracted_data_for_metrics, ground_truth_data)

        results.append({
            "pdf_file": pdf_filename,
            "processing_time_seconds": processing_time,
            "metrics": individual_metrics # This now holds the rich metrics from calculate_overall_metrics
        })
        overall_stats["processed_files"] += 1

    # --- Reporting ---
    # This basic reporting will be enhanced by report_generator.py
    print("\n--- Evaluation Summary (Per File) ---")
    for result_item in results:
        print(f"\nFile: {result_item['pdf_file']}")
        metrics = result_item['metrics']
        print(f"  Insured Name Match: {metrics['insured_name_match']}")
        print(f"    GT: {metrics['insured_name_ground_truth']}")
        print(f"    Extracted: {metrics['insured_name_extracted']}")
        print(f"  Date Metrics (Overall for file):")
        print(f"    Precision: {metrics['summary_stats']['precision_dates']:.2f}, Recall: {metrics['summary_stats']['recall_dates']:.2f}, F1: {metrics['summary_stats']['f1_score_dates']:.2f}")
        print(f"    TP: {metrics['summary_stats']['dates_tp']}, FP: {metrics['summary_stats']['dates_fp']}, FN: {metrics['summary_stats']['dates_fn']}")
        
        for policy_type, p_metrics in metrics['policy_comparison'].items():
            print(f"  Policy: {policy_type}")
            print(f"    Effective Date Correct: {p_metrics['effective_date_correct']} (GT: {p_metrics['effective_date_ground_truth']}, Ext: {p_metrics['effective_date_extracted']})")
            print(f"    Expiration Date Correct: {p_metrics['expiration_date_correct']} (GT: {p_metrics['expiration_date_ground_truth']}, Ext: {p_metrics['expiration_date_extracted']})")

    print("\n--- Aggregated Corpus Statistics & Report Generation ---")
    corpus_summary_metrics = None
    if results:
        corpus_summary_metrics = aggregate_corpus_metrics(results) # Pass the list of result_items
        
        # Console output for aggregated stats (can be made optional)
        print(f"Total Documents Processed: {corpus_summary_metrics['total_documents']}")
        name_match_percentage = (corpus_summary_metrics['total_insured_name_matches'] / corpus_summary_metrics['total_documents'] * 100) if corpus_summary_metrics['total_documents'] > 0 else 0
        print(f"Overall Insured Name Matches: {corpus_summary_metrics['total_insured_name_matches']} ({name_match_percentage:.2f}%)")
        print(f"Overall Date Metrics:")
        print(f"  Precision: {corpus_summary_metrics['overall_precision_dates']:.3f}, Recall: {corpus_summary_metrics['overall_recall_dates']:.3f}, F1-Score: {corpus_summary_metrics['overall_f1_score_dates']:.3f}")
        print(f"  Total TPs: {corpus_summary_metrics['corpus_dates_tp']}, Total FPs: {corpus_summary_metrics['corpus_dates_fp']}, Total FNs: {corpus_summary_metrics['corpus_dates_fn']}")
        print(f"Average Processing Time: {corpus_summary_metrics['average_processing_time']:.2f}s")
        
        print("\n  Policy Type Breakdown (Precision/Recall/F1/Support):")
        for policy_type, data in sorted(corpus_summary_metrics.get("policy_type_breakdown", {}).items()):
            print(f"    {policy_type:<25}: P={data['precision']:.2f}, R={data['recall']:.2f}, F1={data['f1_score']:.2f} (TP:{data['tp']}, FP:{data['fp']}, FN:{data['fn']}, Support Docs:{data['count']})")
    else:
        print("No results to aggregate or report.")

    print("\n--- Raw Overall Statistics (from processing loop) ---")
    print(f"Total PDF files found in corpus: {overall_stats['total_files']}")
    print(f"Successfully processed files (had annotation and parsed): {overall_stats['processed_files']}")
    print(f"Files failed during PDF parsing: {overall_stats['failed_parsing']}")
    print(f"Files with missing annotations: {overall_stats['missing_annotations']}")
    
    # Generate reports
    print("\n--- Generating Reports ---")
    generate_text_summary(corpus_summary_metrics, overall_stats, results, report_dir=reports_output_dir)
    generate_csv_report(results, report_dir=reports_output_dir)
    generate_json_report(corpus_summary_metrics, results, report_dir=reports_output_dir)
    print(f"Reports saved in: {reports_output_dir}")


if __name__ == "__main__": # pragma: no cover
    parser = argparse.ArgumentParser(description="Run COI Auditor Evaluation Harness.")
    parser.add_argument(
        "--corpus_dir",
        type=str,
        default=os.path.join(project_root, "test_harness", "test_corpus"),
        help="Path to the test corpus directory (containing 'pdfs' and 'annotations' subdirectories)."
    )
    parser.add_argument(
        "--reports_dir",
        type=str,
        default=os.path.join(project_root, "test_harness", "reports"),
        help="Path to the directory where evaluation reports will be saved."
    )
    args = parser.parse_args()

    if not os.path.isdir(args.corpus_dir): # pragma: no cover
        print(f"Error: Corpus directory '{args.corpus_dir}' not found or not a directory.")
        print("Please ensure the 'test_corpus' directory exists with 'pdfs' and 'annotations' subdirectories.")
        print(f"Expected structure: {args.corpus_dir}/pdfs and {args.corpus_dir}/annotations")
        sys.exit(1)
        
    run_evaluation(args.corpus_dir, args.reports_dir)