"""
Calculates and aggregates metrics for evaluating COI parsing accuracy against ground truth data.

This module defines functions to:
- Normalize policy type strings.
- Compare extracted dates with ground truth dates.
- Calculate detailed metrics for individual policy types within a document.
- Calculate overall metrics for a single document (including insured name and all policies).
- Aggregate metrics across an entire corpus of documents.
"""
import collections
from typing import Dict, Any, Optional, List, DefaultDict

def normalize_policy_type(policy_type_str: Optional[str]) -> str:
    """Normalizes policy type strings for consistent matching."""
    if not policy_type_str:
        return ""
    return policy_type_str.lower().replace(" ", "_").replace("'", "").replace("-", "_")

def compare_dates(extracted_date: Optional[str], ground_truth_date: Optional[str]) -> bool:
    """
    Compares two date strings.
    Returns True if they match, False otherwise.
    Handles None values gracefully.
    """
    if extracted_date is None and ground_truth_date is None:
        return True # Or False, depending on how "None == None" should be treated. For metrics, often means not found by either.
                    # For this context, if GT is None, and extracted is None, it's not a 'miss' or 'error'.
    return extracted_date == ground_truth_date

def calculate_policy_metrics(extracted_policy: Dict[str, Optional[str]], ground_truth_policy: Dict[str, Optional[str]]) -> Dict[str, Any]:
    """
    Calculates metrics for a single policy type.
    - Correctly found and matching dates.
    - Dates found but incorrect.
    - Dates missed (present in ground truth but not found).
    - Dates found but not in ground truth (false positives - harder to determine without clear "None" meaning).
    """
    metrics = {
        "effective_date_correct": False,
        "expiration_date_correct": False,
        "effective_date_extracted": extracted_policy.get("effective_date"),
        "effective_date_ground_truth": ground_truth_policy.get("effective_date"),
        "expiration_date_extracted": extracted_policy.get("expiration_date"),
        "expiration_date_ground_truth": ground_truth_policy.get("expiration_date"),
        "details": {
            "eff_found_correct": 0, # 1 if found and correct
            "eff_found_incorrect": 0, # 1 if found but not correct
            "eff_missed": 0, # 1 if in GT but not found/None
            "exp_found_correct": 0,
            "exp_found_incorrect": 0,
            "exp_missed": 0,
        }
    }

    # Effective Date
    gt_eff = ground_truth_policy.get("effective_date")
    ext_eff = extracted_policy.get("effective_date")
    if gt_eff:
        if ext_eff:
            if compare_dates(ext_eff, gt_eff):
                metrics["effective_date_correct"] = True
                metrics["details"]["eff_found_correct"] = 1
            else:
                metrics["details"]["eff_found_incorrect"] = 1
        else:
            metrics["details"]["eff_missed"] = 1 # In GT, not extracted
    # Not handling ext_eff but not gt_eff as a specific "false positive" for dates yet,
    # as the parser might extract something for a policy type not in GT.

    # Expiration Date
    gt_exp = ground_truth_policy.get("expiration_date")
    ext_exp = extracted_policy.get("expiration_date")
    if gt_exp:
        if ext_exp:
            if compare_dates(ext_exp, gt_exp):
                metrics["expiration_date_correct"] = True
                metrics["details"]["exp_found_correct"] = 1
            else:
                metrics["details"]["exp_found_incorrect"] = 1
        else:
            metrics["details"]["exp_missed"] = 1 # In GT, not extracted

    return metrics

def calculate_overall_metrics(extracted_data: Dict[str, Any], ground_truth_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compares all extracted data with ground truth data for a single PDF.
    
    Args:
        extracted_data (dict): Data extracted by the parser. 
                               Expected to have policy types as keys (e.g., "general_liability")
                               and values as dicts with "effective_date", "expiration_date".
        ground_truth_data (dict): Ground truth data from the annotation JSON.
                                  Expected to have "insurance_policies" as a list of dicts.

    Returns:
        dict: A dictionary containing detailed metrics.
    """
    results = {
        "insured_name_match": False,
        "insured_name_extracted": extracted_data.get("insured_name", "N/A"),
        "insured_name_ground_truth": ground_truth_data.get("insured_name", "N/A"),
        "policy_comparison": collections.defaultdict(dict),
        "summary_stats": {
            # For dates: TP, FP, FN
            # True Positive (TP): Date in GT, extracted correctly.
            # False Positive (FP): Date extracted, but incorrect OR date extracted for a policy not in GT / GT date is None.
            # False Negative (FN): Date in GT, but not extracted OR extracted as None.
            "total_gt_policy_dates": 0, # Count of effective/expiration dates in GT
            "dates_tp": 0, # Correctly found and matching
            "dates_fp": 0, # Found but incorrect OR found but not in GT
            "dates_fn": 0, # Missed (in GT, not found or None)
        }
    }

    # Compare Insured Name
    # Simple exact match for now. Fuzzy matching could be added.
    if results["insured_name_extracted"] and results["insured_name_ground_truth"]:
        results["insured_name_match"] = (
            results["insured_name_extracted"].strip().lower() == 
            results["insured_name_ground_truth"].strip().lower()
        )

    gt_policies_map = {
        normalize_policy_type(p["policy_type"]): p 
        for p in ground_truth_data.get("insurance_policies", [])
    }
    
    # Iterate through ground truth policies to ensure all are checked
    for gt_norm_type, gt_policy in gt_policies_map.items():
        original_gt_policy_type = gt_policy["policy_type"] # For reporting
        results["summary_stats"]["total_gt_policy_dates"] += 2 # Eff and Exp

        # The `extracted_data` keys from `parse_coi_pdf` might be like 'general_liability', 'workers_compensation'
        # These need to be normalized just like the GT keys for matching.
        # Assuming `extracted_data` keys are already somewhat normalized (e.g., 'general_liability')
        # If `parse_coi_pdf` returns a different structure, this part needs adjustment.
        extracted_policy_data = extracted_data.get(gt_norm_type, {}) 
        if not extracted_policy_data and original_gt_policy_type in extracted_data: # try original name if normalized failed
             extracted_policy_data = extracted_data.get(original_gt_policy_type, {})


        policy_metrics = calculate_policy_metrics(extracted_policy_data, gt_policy)
        results["policy_comparison"][original_gt_policy_type] = policy_metrics
        
        # Aggregate summary stats
        results["summary_stats"]["dates_tp"] += policy_metrics["details"]["eff_found_correct"]
        results["summary_stats"]["dates_tp"] += policy_metrics["details"]["exp_found_correct"]
        
        results["summary_stats"]["dates_fp"] += policy_metrics["details"]["eff_found_incorrect"]
        results["summary_stats"]["dates_fp"] += policy_metrics["details"]["exp_found_incorrect"]
        
        results["summary_stats"]["dates_fn"] += policy_metrics["details"]["eff_missed"]
        results["summary_stats"]["dates_fn"] += policy_metrics["details"]["exp_missed"]

    # Check for policies in extracted_data that are NOT in ground_truth_data (potential FPs for policy types)
    # This requires knowing the structure of `extracted_data` more precisely.
    # For now, focusing on matching GT policies.
    # If `extracted_data` has a policy like "excess_liability" with dates,
    # and GT doesn't list "excess_liability", those dates could be FPs.

    # Calculate Precision, Recall, F1 for dates
    tp = results["summary_stats"]["dates_tp"]
    fp = results["summary_stats"]["dates_fp"]
    fn = results["summary_stats"]["dates_fn"]

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    results["summary_stats"]["precision_dates"] = precision
    results["summary_stats"]["recall_dates"] = recall
    results["summary_stats"]["f1_score_dates"] = f1_score
    
    return results

def aggregate_corpus_metrics(all_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregates metrics from all processed PDFs in the corpus.
    
    Args:
        all_results (list): A list of metric dictionaries, one for each PDF, 
                            as returned by calculate_overall_metrics.
                            
    Returns:
        dict: Aggregated metrics for the entire corpus.
    """
    corpus_summary = {
        "total_documents": len(all_results),
        "total_insured_name_matches": 0,
        "corpus_dates_tp": 0,
        "corpus_dates_fp": 0,
        "corpus_dates_fn": 0,
        "average_processing_time": 0.0,
        "policy_type_breakdown": collections.defaultdict(
            lambda: {"tp": 0, "fp": 0, "fn": 0, "count": 0, "precision": 0.0, "recall": 0.0, "f1_score": 0.0}
        )
    }

    if not all_results:
        return corpus_summary

    total_time = 0
    for res_item in all_results: # res_item is the dict from evaluate.py's results list
        doc_metrics = res_item["metrics"] # This is the output of calculate_overall_metrics
        
        if doc_metrics["insured_name_match"]:
            corpus_summary["total_insured_name_matches"] += 1
        
        corpus_summary["corpus_dates_tp"] += doc_metrics["summary_stats"]["dates_tp"]
        corpus_summary["corpus_dates_fp"] += doc_metrics["summary_stats"]["dates_fp"]
        corpus_summary["corpus_dates_fn"] += doc_metrics["summary_stats"]["dates_fn"]
        total_time += res_item.get("processing_time_seconds", 0)

        for policy_type, p_metrics in doc_metrics["policy_comparison"].items():
            norm_policy_type = normalize_policy_type(policy_type)
            corpus_summary["policy_type_breakdown"][policy_type]["tp"] += p_metrics["details"]["eff_found_correct"] + p_metrics["details"]["exp_found_correct"]
            corpus_summary["policy_type_breakdown"][policy_type]["fp"] += p_metrics["details"]["eff_found_incorrect"] + p_metrics["details"]["exp_found_incorrect"]
            corpus_summary["policy_type_breakdown"][policy_type]["fn"] += p_metrics["details"]["eff_missed"] + p_metrics["details"]["exp_missed"]
            corpus_summary["policy_type_breakdown"][policy_type]["count"] +=1


    corpus_summary["average_processing_time"] = total_time / len(all_results) if len(all_results) > 0 else 0

    # Overall Precision, Recall, F1 for dates
    tp_all = corpus_summary["corpus_dates_tp"]
    fp_all = corpus_summary["corpus_dates_fp"]
    fn_all = corpus_summary["corpus_dates_fn"]

    corpus_summary["overall_precision_dates"] = tp_all / (tp_all + fp_all) if (tp_all + fp_all) > 0 else 0
    corpus_summary["overall_recall_dates"] = tp_all / (tp_all + fn_all) if (tp_all + fn_all) > 0 else 0
    corpus_summary["overall_f1_score_dates"] = (
        2 * (corpus_summary["overall_precision_dates"] * corpus_summary["overall_recall_dates"]) /
        (corpus_summary["overall_precision_dates"] + corpus_summary["overall_recall_dates"])
        if (corpus_summary["overall_precision_dates"] + corpus_summary["overall_recall_dates"]) > 0 else 0
    )
    
    for pt, data in corpus_summary["policy_type_breakdown"].items():
        pt_tp = data["tp"]
        pt_fp = data["fp"]
        pt_fn = data["fn"]
        data["precision"] = pt_tp / (pt_tp + pt_fp) if (pt_tp + pt_fp) > 0 else 0
        data["recall"] = pt_tp / (pt_tp + pt_fn) if (pt_tp + pt_fn) > 0 else 0
        data["f1_score"] = (2 * data["precision"] * data["recall"]) / (data["precision"] + data["recall"]) if (data["precision"] + data["recall"]) > 0 else 0


    return corpus_summary

if __name__ == '__main__':
    # Example Usage (for testing this module directly)
    # This would typically be called by evaluate.py

    # Mock extracted data (what your parser might output)
    mock_extracted = {
        "insured_name": "Accurate Builders Inc.",
        "general_liability": {"effective_date": "2023-01-01", "expiration_date": "2024-01-01"},
        "workers_compensation": {"effective_date": "2023-03-01", "expiration_date": "2024-02-28"}, # Incorrect exp date
        "automobile_liability": {"effective_date": "2023-01-15", "expiration_date": None} # Missed exp date
    }

    # Mock ground truth data (from your JSON annotation)
    mock_ground_truth = {
      "file_name": "example.pdf",
      "insured_name": "Accurate Builders Inc.",
      "insurance_policies": [
        {
          "policy_type": "General Liability",
          "effective_date": "2023-01-01",
          "expiration_date": "2024-01-01"
        },
        {
          "policy_type": "Workers Compensation",
          "effective_date": "2023-03-01",
          "expiration_date": "2024-03-01"
        },
        {
          "policy_type": "Automobile Liability",
          "effective_date": "2023-01-15",
          "expiration_date": "2024-01-15"
        },
        { # Policy in GT but not extracted
          "policy_type": "Umbrella Liability",
          "effective_date": "2023-01-01",
          "expiration_date": "2024-01-01"
        }
      ]
    }

    print("--- Individual PDF Metrics ---")
    individual_metrics = calculate_overall_metrics(mock_extracted, mock_ground_truth)
    import json
    print(json.dumps(individual_metrics, indent=2))

    # Mock for corpus aggregation
    mock_results_list = [
        {
            "pdf_file": "doc1.pdf", 
            "processing_time_seconds": 1.5, 
            "metrics": individual_metrics # use the same metrics for simplicity
        },
        # Add more mock results if needed
    ]
    print("\n--- Aggregated Corpus Metrics ---")
    corpus_agg_metrics = aggregate_corpus_metrics(mock_results_list)
    print(json.dumps(corpus_agg_metrics, indent=2))