"""
Generates various report formats (text, CSV, JSON) from COI evaluation metrics.

This module takes aggregated corpus metrics and detailed per-file results
to produce human-readable summaries and machine-parsable data files.
"""
import json
import csv
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

# Attempt to import from metrics_calculator for normalize_policy_type if needed
try:
    from .metrics_calculator import normalize_policy_type
except ImportError: # Fallback for direct execution
    # This fallback might not work if metrics_calculator itself has relative imports
    # and is not in the Python path when report_generator is run directly.
    # For robustness, it's better if these scripts are run as part of a package
    # or with PYTHONPATH set correctly.
    from metrics_calculator import normalize_policy_type


def generate_text_summary(
    corpus_summary_metrics: Optional[Dict[str, Any]],
    overall_stats: Dict[str, Any],
    results_per_file: List[Dict[str, Any]],
    report_dir: str = "."
) -> str:
    """
    Generates a detailed text summary of the evaluation results.
    """
    lines = []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append(f"COI Auditor Evaluation Report - {timestamp}")
    lines.append("=" * 40)

    lines.append("\n--- Overall Corpus Statistics ---")
    if corpus_summary_metrics:
        lines.append(f"Total Documents Processed: {corpus_summary_metrics['total_documents']}")
        name_match_percentage = (corpus_summary_metrics['total_insured_name_matches'] / corpus_summary_metrics['total_documents'] * 100) if corpus_summary_metrics['total_documents'] > 0 else 0
        lines.append(f"Overall Insured Name Matches: {corpus_summary_metrics['total_insured_name_matches']} ({name_match_percentage:.2f}%)")
        lines.append(f"Overall Date Metrics:")
        lines.append(f"  Precision: {corpus_summary_metrics['overall_precision_dates']:.3f}")
        lines.append(f"  Recall:    {corpus_summary_metrics['overall_recall_dates']:.3f}")
        lines.append(f"  F1-Score:  {corpus_summary_metrics['overall_f1_score_dates']:.3f}")
        lines.append(f"  Total TPs: {corpus_summary_metrics['corpus_dates_tp']}, Total FPs: {corpus_summary_metrics['corpus_dates_fp']}, Total FNs: {corpus_summary_metrics['corpus_dates_fn']}")
        lines.append(f"Average Processing Time: {corpus_summary_metrics['average_processing_time']:.2f}s per document")

        lines.append("\n  Policy Type Breakdown (Precision/Recall/F1/Support):")
        for policy_type, data in sorted(corpus_summary_metrics.get("policy_type_breakdown", {}).items()):
            lines.append(f"    {policy_type:<25}: P={data['precision']:.2f}, R={data['recall']:.2f}, F1={data['f1_score']:.2f} (TP:{data['tp']}, FP:{data['fp']}, FN:{data['fn']}, Support Docs:{data['count']})")
    else:
        lines.append("No aggregated corpus metrics available.")

    lines.append("\n--- Raw Processing Statistics ---")
    lines.append(f"Total PDF files found in corpus: {overall_stats['total_files']}")
    lines.append(f"Successfully processed (annotation found & parsed): {overall_stats['processed_files']}")
    lines.append(f"Files failed during PDF parsing stage: {overall_stats['failed_parsing']}")
    lines.append(f"Files with missing annotations: {overall_stats['missing_annotations']}")

    lines.append("\n--- Detailed Per-File Results ---")
    for result_item in results_per_file:
        lines.append(f"\nFile: {result_item['pdf_file']}")
        metrics = result_item['metrics']
        lines.append(f"  Processing Time: {result_item['processing_time_seconds']:.2f}s")
        lines.append(f"  Insured Name Match: {metrics['insured_name_match']} (GT: '{metrics['insured_name_ground_truth']}', Ext: '{metrics['insured_name_extracted']}')")
        lines.append(f"  File Date Metrics: P={metrics['summary_stats']['precision_dates']:.2f}, R={metrics['summary_stats']['recall_dates']:.2f}, F1={metrics['summary_stats']['f1_score_dates']:.2f} (TP:{metrics['summary_stats']['dates_tp']}, FP:{metrics['summary_stats']['dates_fp']}, FN:{metrics['summary_stats']['dates_fn']})")
        for policy_type, p_metrics in sorted(metrics['policy_comparison'].items()):
            lines.append(f"    {policy_type:<25}:")
            lines.append(f"      Effective Date: {'Correct' if p_metrics['effective_date_correct'] else 'INCORRECT'}")
            lines.append(f"        GT: {p_metrics['effective_date_ground_truth']:<12} Ext: {p_metrics['effective_date_extracted']}")
            lines.append(f"      Expiration Date: {'Correct' if p_metrics['expiration_date_correct'] else 'INCORRECT'}")
            lines.append(f"        GT: {p_metrics['expiration_date_ground_truth']:<12} Ext: {p_metrics['expiration_date_extracted']}")
    
    report_content = "\n".join(lines)
    
    # Save to file
    report_path = os.path.join(report_dir, "evaluation_summary.txt")
    try:
        with open(report_path, "w") as f:
            f.write(report_content)
        print(f"Text summary report saved to: {report_path}")
    except IOError as e:
        print(f"Error saving text summary report: {e}")
        
    return report_content # Also return as string for potential console output


def generate_csv_report(results_per_file: List[Dict[str, Any]], report_dir: str = "."):
    """
    Generates a CSV report with detailed results per PDF and per policy type.
    """
    if not results_per_file:
        print("No results to generate CSV report.")
        return

    timestamp_fn = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file_path = os.path.join(report_dir, f"evaluation_details_{timestamp_fn}.csv")

    fieldnames = [
        "pdf_file",
        "processing_time_seconds",
        "insured_name_match",
        "insured_name_ground_truth",
        "insured_name_extracted",
        "file_date_precision",
        "file_date_recall",
        "file_date_f1",
        "file_dates_tp",
        "file_dates_fp",
        "file_dates_fn",
        "policy_type",
        "eff_date_correct",
        "eff_date_gt",
        "eff_date_ext",
        "exp_date_correct",
        "exp_date_gt",
        "exp_date_ext"
    ]

    try:
        with open(csv_file_path, "w", newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for result_item in results_per_file:
                metrics = result_item['metrics']
                base_row_data = {
                    "pdf_file": result_item['pdf_file'],
                    "processing_time_seconds": f"{result_item['processing_time_seconds']:.2f}",
                    "insured_name_match": metrics['insured_name_match'],
                    "insured_name_ground_truth": metrics['insured_name_ground_truth'],
                    "insured_name_extracted": metrics['insured_name_extracted'],
                    "file_date_precision": f"{metrics['summary_stats']['precision_dates']:.3f}",
                    "file_date_recall": f"{metrics['summary_stats']['recall_dates']:.3f}",
                    "file_date_f1": f"{metrics['summary_stats']['f1_score_dates']:.3f}",
                    "file_dates_tp": metrics['summary_stats']['dates_tp'],
                    "file_dates_fp": metrics['summary_stats']['dates_fp'],
                    "file_dates_fn": metrics['summary_stats']['dates_fn'],
                }
                
                if not metrics['policy_comparison']: # If no policies were compared for this file
                    row = base_row_data.copy()
                    row["policy_type"] = "N/A"
                    writer.writerow(row)
                else:
                    for policy_type, p_metrics in metrics['policy_comparison'].items():
                        row = base_row_data.copy()
                        row["policy_type"] = policy_type
                        row["eff_date_correct"] = p_metrics['effective_date_correct']
                        row["eff_date_gt"] = p_metrics['effective_date_ground_truth']
                        row["eff_date_ext"] = p_metrics['effective_date_extracted']
                        row["exp_date_correct"] = p_metrics['expiration_date_correct']
                        row["exp_date_gt"] = p_metrics['expiration_date_ground_truth']
                        row["exp_date_ext"] = p_metrics['expiration_date_extracted']
                        writer.writerow(row)
        
        print(f"CSV detailed report saved to: {csv_file_path}")
    except IOError as e:
        print(f"Error saving CSV report: {e}")


def generate_json_report(
    corpus_summary_metrics: Optional[Dict[str, Any]],
    results_per_file: List[Dict[str, Any]],
    report_dir: str = "."
):
    """
    Generates a JSON report containing both aggregated and per-file results.
    """
    timestamp_fn = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_file_path = os.path.join(report_dir, f"evaluation_results_{timestamp_fn}.json")
    
    full_report = {
        "report_generated_at": datetime.now().isoformat(),
        "corpus_summary": corpus_summary_metrics,
        "detailed_results_per_file": results_per_file
    }
    
    try:
        with open(json_file_path, "w") as f:
            json.dump(full_report, f, indent=2)
        print(f"JSON report saved to: {json_file_path}")
    except IOError as e:
        print(f"Error saving JSON report: {e}")
    except TypeError as e:
        print(f"Error serializing JSON report: {e}. Check data types.")


if __name__ == '__main__': # pragma: no cover
    # Mock data for testing report generation
    mock_overall_stats = {
        "total_files": 2, "processed_files": 1, "failed_parsing": 0, "missing_annotations": 1
    }
    mock_corpus_summary = {
        'total_documents': 1, 'total_insured_name_matches': 1, 
        'corpus_dates_tp': 2, 'corpus_dates_fp': 1, 'corpus_dates_fn': 3, 
        'average_processing_time': 1.5, 
        'overall_precision_dates': 0.666, 'overall_recall_dates': 0.4, 'overall_f1_score_dates': 0.5,
        'policy_type_breakdown': {
            'General Liability': {'tp': 1, 'fp': 0, 'fn': 0, 'count': 1, 'precision': 1.0, 'recall': 1.0, 'f1_score': 1.0},
            'Workers Compensation': {'tp': 0, 'fp': 1, 'fn': 1, 'count': 1, 'precision': 0.0, 'recall': 0.0, 'f1_score': 0.0},
        }
    }
    mock_results_per_file = [
        {
            "pdf_file": "doc1.pdf", 
            "processing_time_seconds": 1.5, 
            "metrics": {
                "insured_name_match": True,
                "insured_name_extracted": "Builder", "insured_name_ground_truth": "Builder",
                "summary_stats": {'dates_tp': 2, 'dates_fp': 1, 'dates_fn': 3, 'precision_dates': 0.666, 'recall_dates': 0.4, 'f1_score_dates': 0.5},
                "policy_comparison": {
                    "General Liability": {
                        "effective_date_correct": True, "effective_date_extracted": "2023-01-01", "effective_date_ground_truth": "2023-01-01",
                        "expiration_date_correct": True, "expiration_date_extracted": "2024-01-01", "expiration_date_ground_truth": "2024-01-01",
                    },
                    "Workers Compensation": {
                        "effective_date_correct": False, "effective_date_extracted": "2023-03-01", "effective_date_ground_truth": "2023-03-15", # Incorrect
                        "expiration_date_correct": True, "expiration_date_extracted": "2024-03-01", "expiration_date_ground_truth": "2024-03-01",
                    }
                }
            }
        }
    ]

    print("--- Generating Text Summary ---")
    generate_text_summary(mock_corpus_summary, mock_overall_stats, mock_results_per_file)
    print("\n--- Generating CSV Report ---")
    generate_csv_report(mock_results_per_file)
    print("\n--- Generating JSON Report ---")
    generate_json_report(mock_corpus_summary, mock_results_per_file)