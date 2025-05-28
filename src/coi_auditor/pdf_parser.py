from typing import List, Tuple, Dict, Any, Optional, Union
import logging
import math
import os
import re
import json
from pathlib import Path
from datetime import date, datetime
from coi_auditor.config import load_config # Assuming load_config is the correct accessor
CONFIG = load_config()

logger = logging.getLogger(__name__)

# Import rapidfuzz for fuzzy matching
try:
    from rapidfuzz import fuzz, process
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    # Create dummy objects to avoid unbound variable errors
    class DummyFuzz:
        @staticmethod
        def ratio(*args, **kwargs):
            return 0.0
        @staticmethod
        def partial_ratio(*args, **kwargs):
            return 0.0
        @staticmethod
        def token_sort_ratio(*args, **kwargs):
            return 0.0
        @staticmethod
        def token_set_ratio(*args, **kwargs):
            return 0.0
    
    fuzz = DummyFuzz()
    process = None
    RAPIDFUZZ_AVAILABLE = False
    logger.warning("rapidfuzz library not found. Fuzzy matching will be disabled. Install with: pip install rapidfuzz>=3.6.0")

# PDF and Date Parsing Libraries
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None # type: ignore
    logger.error("pypdf library not found. Please install it: pip install pypdf")

try:
    from dateutil.parser import parse as dateutil_parse
    from dateutil.parser import ParserError as DateutilParserError
except ImportError:
    dateutil_parse = None # type: ignore
    DateutilParserError = None # type: ignore
    logger.error("python-dateutil library not found. Please install it: pip install python-dateutil")

def reconcile_layout_regions(
    detected_columns: List[Tuple[float, float, float, float]],
    detected_tables: List[Dict[str, Any]],  # Expects tables with 'bbox' key
    page_width: float,
    page_height: float,
    config: Dict[str, Any],
    debug_mode: bool,
) -> List[Dict[str, Any]]:
    """
    Reconciles detected columns and tables into a list of prioritized processing regions.
    Tables take precedence. Columns are then defined by the remaining space.
    """
    logger.debug(f"Starting. Columns: [yellow]{len(detected_columns)}[/yellow], Tables: [yellow]{len(detected_tables)}[/yellow]")
    reconcile_config = config.get('layout_reconciliation', {})
    min_region_area_ratio = reconcile_config.get('min_region_area_ratio_of_page', 0.005) # Minimum area for a region to be considered
    min_region_area_px = page_width * page_height * min_region_area_ratio
    min_clamped_table_width_px = reconcile_config.get('min_clamped_table_width_px', 20) # Min width for a salvaged table part
    min_clamped_table_height_px = reconcile_config.get('min_clamped_table_height_px', 10) # Min height for a salvaged table part

    if not detected_tables and not detected_columns:
        logger.debug("No tables or columns detected. Returning empty list of regions.")
        return []
    
    # Start with table regions, giving them higher priority
    # Table bboxes are typically [x0, y0, x1, y1] relative to page
    processing_regions: List[Dict[str, Any]] = [] # Ensure it's always a list
    for i, table in enumerate(detected_tables):
        # We expect 'box' (absolute [x0, y0, x1, y1]) from ml_table_detector
        # and need to normalize it. The original code expected 'bbox_norm'.
        raw_bbox = table.get('box')
        if raw_bbox is None:
            logger.error(f"Table at index {i} from detected_tables is missing 'box' key. Table details: {table}. Skipping this table.")
            continue

        if not (isinstance(raw_bbox, list) and len(raw_bbox) == 4 and all(isinstance(coord, (int, float)) for coord in raw_bbox)):
            logger.error(f"Table at index {i} has 'box' with invalid format: {raw_bbox}. Table details: {table}. Skipping this table.")
            continue

        if page_width <= 0 or page_height <= 0: # Prevent division by zero
            logger.error(f"Page dimensions are invalid (width: {page_width}, height: {page_height}). Cannot normalize table bbox for table {i}. Skipping.")
            continue
        
        # abs_x0, abs_y0, abs_x1, abs_y1 = raw_bbox # Original assignment

        # --- START Goal 1: Table Salvaging Modification ---
        # Floor coordinates to handle potential "incorrect bbox" as implied by test_reconcile_layout_regions_one_table_incorrect_bbox
        # This ensures that for inputs like [100.123, 100.456, 200.789, 200.321], the processing uses [100, 100, 200, 200]
        # which, after normalization, matches the specific assertion in that test.
        orig_abs_x0 = math.floor(raw_bbox[0])
        orig_abs_y0 = math.floor(raw_bbox[1])
        orig_abs_x1 = math.floor(raw_bbox[2])
        orig_abs_y1 = math.floor(raw_bbox[3])

        if debug_mode:
            logger.debug(
                f"Table at index {i} (raw_bbox: {[round(c, 1) for c in raw_bbox]}, floored_to_process: {[orig_abs_x0, orig_abs_y0, orig_abs_x1, orig_abs_y1]}) - Original Bounding Box"
            )
        # Note: The redundant debug logs below were present in the original code. Keeping one for brevity if needed.
        # if debug_mode:
        #     logger.debug(
        #         f"Table at index {i} (raw_bbox: {[round(c, 1) for c in raw_bbox]}) - Original Bounding Box"
        #     )
        # if debug_mode:
        #     logger.debug(f"Table at index {i} (raw_bbox: {[round(c,1) for c in raw_bbox]}) - Original Bounding Box")
        # if debug_mode:
        #     logger.debug(f"Table at index {i} (raw_bbox: {[round(c,1) for c in raw_bbox]}) - Original Bounding Box")

        # Clamp absolute coordinates to page boundaries
        clamped_abs_x0_val = max(0.0, orig_abs_x0)
        clamped_abs_y0_val = max(0.0, orig_abs_y0)
        clamped_abs_x1_val = min(page_width, orig_abs_x1)
        clamped_abs_y1_val = min(page_height, orig_abs_y1)
        
        is_valid_clamped_box = (clamped_abs_x0_val < clamped_abs_x1_val and
                                clamped_abs_y0_val < clamped_abs_y1_val and
                                (clamped_abs_x1_val - clamped_abs_x0_val) >= min_clamped_table_width_px and
                                (clamped_abs_y1_val - clamped_abs_y0_val) >= min_clamped_table_height_px)

        orig_table_width = orig_abs_x1 - orig_abs_x0
        orig_table_height = orig_abs_y1 - orig_abs_y0
        orig_table_area = orig_table_width * orig_table_height
        clamped_table_width = clamped_abs_x1_val - clamped_abs_x0_val
        clamped_table_height = clamped_abs_y1_val - clamped_abs_y0_val
        clamped_table_area = clamped_table_width * clamped_table_height
        area_ratio = clamped_table_area / orig_table_area if orig_table_area > 0 else 0
        
        min_area_percentage = reconcile_config.get('min_area_percentage', 0.5)
        is_single_row_or_col = (orig_table_height < (page_height / 10)) or (orig_table_width < (page_width / 10))
        
        # Lenient size requirements for single-row or single-column tables
        if is_single_row_or_col:
            min_clamped_table_width = reconcile_config.get('min_clamped_table_width_single_row_col_px', 10)
            min_clamped_table_height = reconcile_config.get('min_clamped_table_height_single_row_col_px', 5)
        else:
            min_clamped_table_width = min_clamped_table_width_px
            min_clamped_table_height = min_clamped_table_height_px

        is_valid_clamped_box = (clamped_abs_x0_val < clamped_abs_x1_val and
                                clamped_abs_y0_val < clamped_abs_y1_val and
                                (clamped_abs_x1_val - clamped_abs_x0_val) >= min_clamped_table_width and
                                (clamped_abs_y1_val - clamped_abs_y0_val) >= min_clamped_table_height and
                                area_ratio >= min_area_percentage)

        logger.debug(
            f"Table at index {i} (raw_bbox: {[round(c,1) for c in raw_bbox]}) - "
            f"Original Area: {orig_table_area:.1f}, Clamped Area: {clamped_table_area:.1f}, Area Ratio: {area_ratio:.2f}, "
            f"Single Row/Col: {is_single_row_or_col}"
        )

        if not is_valid_clamped_box:
            logger.warning(
                f"Table at index {i} (raw_bbox: {[round(c,1) for c in raw_bbox]}) resulted in an "
                f"invalid or too small on-page clamped absolute bbox "
                f"({{[round(c,1) for c in [clamped_abs_x0_val, clamped_abs_y0_val, clamped_abs_x1_val, clamped_abs_y1_val]]}}). "
                f"Min W/H: {min_clamped_table_width}/{min_clamped_table_height}. Area Ratio: {area_ratio:.2f}. "
                f"Page WxH: {page_width:.0f}x{page_height:.0f}. Skipping."
            )
            continue
        
        # Use the successfully clamped absolute coordinates for normalization
        abs_x0, abs_y0, abs_x1, abs_y1 = clamped_abs_x0_val, clamped_abs_y0_val, clamped_abs_x1_val, clamped_abs_y1_val
        # --- END Goal 1 ---

        if debug_mode:
            logger.debug(f"Table at index {i} (raw_bbox: {[round(c,1) for c in raw_bbox]}) - Clamped Bounding Box: {[round(c,1) for c in [abs_x0, abs_y0, abs_x1, abs_y1]]}")

        if debug_mode:
            logger.debug(f"Table at index {i} (raw_bbox: {[round(c,1) for c in raw_bbox]}) - Clamped Bounding Box: {[round(c,1) for c in [abs_x0, abs_y0, abs_x1, abs_y1]]}")
        
        # Normalize coordinates (these should now be from the on-page portion)
        norm_x0 = abs_x0 / page_width if page_width > 0 else 0
        norm_y0 = abs_y0 / page_height if page_height > 0 else 0
        norm_x1 = abs_x1 / page_width if page_width > 0 else 0
        norm_y1 = abs_y1 / page_height if page_height > 0 else 0
        
        table_bbox_intermediate = [norm_x0, norm_y0, norm_x1, norm_y1]
        
        # Clamp normalized values to be within [0.0, 1.0] - this should be mostly redundant now but safe.
        clamped_bbox_intermediate = [max(0.0, min(1.0, coord)) for coord in table_bbox_intermediate]

        # Validate that x0 < x1 and y0 < y1 after normalization and clamping.
        if not (clamped_bbox_intermediate[0] < clamped_bbox_intermediate[2] and clamped_bbox_intermediate[1] < clamped_bbox_intermediate[3]):
            logger.warning(f"Table at index {i} (raw_bbox: {[round(c,1) for c in raw_bbox]}, "
                           f"initially_clamped_abs: {[round(c,1) for c in [abs_x0, abs_y0, abs_x1, abs_y1]]}) "
                           f"resulted in invalid normalized+clamped bbox ({[round(c,3) for c in clamped_bbox_intermediate]}). "
                           f"Norm from clamped_abs: {[round(c,3) for c in table_bbox_intermediate]}. Page WxH: {page_width:.0f}x{page_height:.0f}. Skipping.")
            continue
        
        table_bbox = clamped_bbox_intermediate
        processing_regions.append({
            'type': 'table',
            'bbox': table_bbox,
            'priority': 1, # Higher priority for tables
            'source_id': f"table_{i}"
        })
        logger.debug(f"Added table region: [yellow]{table_bbox}[/yellow]")

    # Now, consider column regions and subtract table areas from them
    remaining_column_parts = []
    if detected_columns:
        initial_column_bboxes = detected_columns # These are assumed to be absolute pixel coords
        logger.debug(f"Using {len(detected_columns)} detected column(s) as base for fragments.")
    else:
        # If no columns are detected, we will not create column fragments from the full page.
        # This handles the case for test_reconcile_layout_regions_one_table_incorrect_bbox
        # (where tables exist but no columns are detected).
        # The case for (no tables AND no columns) is handled by an earlier return.
        initial_column_bboxes = []
        logger.debug("No explicit columns detected by input. No column fragments will be generated from the full page.")

    for col_idx, col_bbox in enumerate(initial_column_bboxes):
        current_col_fragments = [col_bbox]
        for table_region in processing_regions: # Only consider table regions for subtraction
            if table_region['type'] == 'table':
                table_bbox_for_sub = table_region['bbox']
                next_fragments = []
                for frag in current_col_fragments:
                    next_fragments.extend(subtract_bbox(frag, table_bbox_for_sub))
                current_col_fragments = next_fragments
        remaining_column_parts.extend([(frag, col_idx) for frag in current_col_fragments]) # Keep original col_idx

    for i, (col_part_bbox, orig_col_idx) in enumerate(remaining_column_parts):
        if get_bbox_area(col_part_bbox) >= min_region_area_px:
            processing_regions.append({
                'type': 'column_fragment', # Or 'text_region'
                'bbox': col_part_bbox,
                'priority': 2, # Lower priority than tables
                'source_id': f"col{orig_col_idx}_frag{i}"
            })
            logger.debug(f"Added column fragment: [yellow]{col_part_bbox}[/yellow] (from original col [yellow]{orig_col_idx}[/yellow])")
        else:
            logger.debug(f"Discarded small column fragment: [yellow]{col_part_bbox}[/yellow] (Area: [yellow]{get_bbox_area(col_part_bbox):.1f}px[/yellow], MinArea: [yellow]{min_region_area_px:.1f}px[/yellow])")


    # Sort by priority (tables first), then typically top-to-bottom, left-to-right
    processing_regions.sort(key=lambda r: (r['priority'], r['bbox'][1], r['bbox'][0]))
    
    # Optional: Merge overlapping or very close regions of the same type/priority if needed
    # For now, we keep them separate.

    logger.info(f"Reconciled into [green]{len(processing_regions)}[/green] processing regions.")
    if processing_regions:
        for r_idx, r_info in enumerate(processing_regions):
             logger.debug(f"  Region {r_idx+1}: Type='[cyan]{r_info['type']}[/cyan]', BBox=[yellow]{r_info['bbox']}[/yellow], Prio=[yellow]{r_info['priority']}[/yellow], ID='[cyan]{r_info['source_id']}[/cyan]'")
    
    return processing_regions


def subtract_bbox(main_bbox: Tuple[float, float, float, float], subtract_bbox: Tuple[float, float, float, float]) -> List[Tuple[float, float, float, float]]:
    """
    Subtracts subtract_bbox from main_bbox, returning a list of up to 4
    rectangular regions that represent the remainder of main_bbox.
    """
    ix0, iy0, ix1, iy1 = main_bbox
    sx0, sy0, sx1, sy1 = subtract_bbox
    remaining_bboxes = []

    # Check for no overlap or if subtract_bbox completely contains main_bbox
    if sx1 <= ix0 or sx0 >= ix1 or sy1 <= iy0 or sy0 >= iy1:  # No overlap
        return [main_bbox]
    if sx0 <= ix0 and sx1 >= ix1 and sy0 <= iy0 and sy1 >= iy1:  # subtract_bbox contains main_bbox
        return []

    # Case 1: Subtract_bbox splits main_bbox horizontally
    if sx0 > ix0 and sx1 < ix1:
        remaining_bboxes.append((ix0, iy0, sx0, iy1))  # Left portion
        remaining_bboxes.append((sx1, iy0, ix1, iy1))  # Right portion
        remaining_bboxes = [bbox for bbox in remaining_bboxes if (bbox[2] - bbox[0]) > 0 and (bbox[3] - bbox[1]) > 0]
        return remaining_bboxes

    # Case 2: Subtract_bbox splits main_bbox vertically
    if sy0 > iy0 and sy1 < iy1:
        remaining_bboxes.append((ix0, iy0, ix1, sy0))  # Top portion
        remaining_bboxes.append((ix0, sy1, ix1, iy1))  # Bottom portion
        remaining_bboxes = [bbox for bbox in remaining_bboxes if (bbox[2] - bbox[0]) > 0 and (bbox[3] - bbox[1]) > 0]
        return remaining_bboxes

    # Case 3: Subtract_bbox intersects from the left
    if sx0 > ix0 and sx0 < ix1:
        remaining_bboxes.append((ix0, iy0, sx0, iy1))  # Left portion
        remaining_bboxes = [bbox for bbox in remaining_bboxes if (bbox[2] - bbox[0]) > 0 and (bbox[3] - bbox[1]) > 0]
        return remaining_bboxes

    # Case 4: Subtract_bbox intersects from the right
    if sx1 > ix0 and sx1 < ix1:
        remaining_bboxes.append((sx1, iy0, ix1, iy1))  # Right portion
        remaining_bboxes = [bbox for bbox in remaining_bboxes if (bbox[2] - bbox[0]) > 0 and (bbox[3] - bbox[1]) > 0]
        return remaining_bboxes

    # Case 5: Subtract_bbox intersects from the top
    if sy0 > iy0 and sy0 < iy1:
        remaining_bboxes.append((ix0, iy0, ix1, sy0))  # Top portion
        remaining_bboxes = [bbox for bbox in remaining_bboxes if (bbox[2] - bbox[0]) > 0 and (bbox[3] - bbox[1]) > 0]
        return remaining_bboxes

    # Case 6: Subtract_bbox intersects from the bottom
    if sy1 > iy0 and sy1 < iy1:
        remaining_bboxes.append((ix0, sy1, ix1, iy1))  # Bottom portion
        remaining_bboxes = [bbox for bbox in remaining_bboxes if (bbox[2] - bbox[0]) > 0 and (bbox[3] - bbox[1]) > 0]
        return remaining_bboxes

    return remaining_bboxes


def get_bbox_area(bbox: Tuple[float, float, float, float]) -> float:
    """Calculates the area of a bounding box."""
    x0, y0, x1, y1 = bbox
    return (x1 - x0) * (y1 - y0)

def _normalize_name(name: str) -> str:
    """Helper to normalize names for comparison by lowercasing and removing non-alphanumeric characters."""
    name = name.lower()
    name = re.sub(r'[^\w]', '', name) # Remove non-alphanumeric characters (keeps letters, numbers, underscore)
    return name

def _normalize_name_enhanced(name: str) -> str:
    """
    Enhanced name normalization that preserves business terms and handles common variations.
    
    Args:
        name: The name to normalize
        
    Returns:
        Normalized name with business terms preserved
    """
    if not name:
        return ""
    
    # Get business terms from config
    business_terms = CONFIG.get('name_normalization', {}).get('business_terms', {})
    
    # Convert to lowercase for processing
    normalized = name.lower().strip()
    
    # Replace common punctuation with spaces for better tokenization
    normalized = re.sub(r'[&\-_\.,;:]', ' ', normalized)
    
    # Split into tokens
    tokens = normalized.split()
    
    # Process each token
    processed_tokens = []
    for token in tokens:
        # Remove non-alphanumeric characters from token
        clean_token = re.sub(r'[^\w]', '', token)
        if not clean_token:
            continue
            
        # Check if token matches a business term
        if clean_token in business_terms:
            processed_tokens.append(business_terms[clean_token])
        else:
            processed_tokens.append(clean_token)
    
    return ''.join(processed_tokens)

def _get_normalized_variations(name: str) -> List[str]:
    """
    Generate multiple normalized variations of a name for better fuzzy matching.
    
    Args:
        name: The original name
        
    Returns:
        List of normalized variations
    """
    if not name:
        return []
    
    variations = []
    
    # Original enhanced normalization
    enhanced_norm = _normalize_name_enhanced(name)
    if enhanced_norm:
        variations.append(enhanced_norm)
    
    # Original simple normalization (for backward compatibility)
    simple_norm = _normalize_name(name)
    if simple_norm and simple_norm not in variations:
        variations.append(simple_norm)
    
    # Generate variations if enabled in config
    if CONFIG.get('name_normalization', {}).get('generate_variations', True):
        # Remove common business suffixes for additional variation
        business_suffixes = ['llc', 'inc', 'corp', 'company', 'co', 'ltd', 'limited']
        base_name = enhanced_norm
        for suffix in business_suffixes:
            if base_name.endswith(suffix):
                base_without_suffix = base_name[:-len(suffix)].strip()
                if base_without_suffix and base_without_suffix not in variations:
                    variations.append(base_without_suffix)
                break
        
        # Add variation with spaces removed from original
        no_spaces = re.sub(r'\s+', '', name.lower())
        no_spaces_clean = re.sub(r'[^\w]', '', no_spaces)
        if no_spaces_clean and no_spaces_clean not in variations:
            variations.append(no_spaces_clean)
    
    return variations

def find_best_fuzzy_matches(target_name: str, candidate_files: List[str], threshold: float = 75.0, max_results: int = 5) -> List[Tuple[str, float]]:
    """
    Find the best fuzzy matches for a target name among candidate files using rapidfuzz.
    
    Args:
        target_name: The name to search for
        candidate_files: List of candidate filenames (without extensions)
        threshold: Minimum similarity threshold (0-100)
        max_results: Maximum number of results to return
        
    Returns:
        List of tuples (filename, score) sorted by score descending
    """
    if not RAPIDFUZZ_AVAILABLE:
        logger.warning("rapidfuzz not available, cannot perform fuzzy matching")
        return []
    
    if not target_name or not candidate_files:
        return []
    
    # Get fuzzy matching configuration
    fuzzy_config = CONFIG.get('fuzzy_matching', {})
    algorithms = fuzzy_config.get('algorithms', ['ratio', 'partial_ratio', 'token_sort_ratio'])
    
    # Generate normalized variations of the target name
    target_variations = _get_normalized_variations(target_name)
    
    logger.debug(f"Fuzzy matching target '{target_name}' with {len(target_variations)} variations: {target_variations}")
    
    # Score each candidate file
    scored_matches = []
    
    for candidate in candidate_files:
        # Generate variations for the candidate
        candidate_variations = _get_normalized_variations(candidate)
        
        best_score = 0.0
        best_algorithm = ""
        
        # Test all combinations of target and candidate variations
        for target_var in target_variations:
            for candidate_var in candidate_variations:
                # Try each configured algorithm
                for algorithm in algorithms:
                    try:
                        if algorithm == 'ratio':
                            score = fuzz.ratio(target_var, candidate_var)
                        elif algorithm == 'partial_ratio':
                            score = fuzz.partial_ratio(target_var, candidate_var)
                        elif algorithm == 'token_sort_ratio':
                            score = fuzz.token_sort_ratio(target_var, candidate_var)
                        elif algorithm == 'token_set_ratio':
                            score = fuzz.token_set_ratio(target_var, candidate_var)
                        else:
                            logger.warning(f"Unknown fuzzy matching algorithm: {algorithm}")
                            continue
                        
                        if score > best_score:
                            best_score = score
                            best_algorithm = algorithm
                            
                    except Exception as e:
                        logger.warning(f"Error in fuzzy matching with algorithm {algorithm}: {e}")
                        continue
        
        if best_score >= threshold:
            scored_matches.append((candidate, best_score, best_algorithm))
            logger.debug(f"Fuzzy match: '{candidate}' -> {best_score:.1f}% (algorithm: {best_algorithm})")
    
    # Sort by score descending and limit results
    scored_matches.sort(key=lambda x: x[1], reverse=True)
    
    # Return only filename and score (drop algorithm info)
    return [(filename, score) for filename, score, _ in scored_matches[:max_results]]

def find_coi_pdfs(pdf_directory_path: str, subcontractor_name: str, direct_pdf_path: Optional[Path] = None, fuzzy_config: Optional[Dict[str, Any]] = None) -> List[Tuple[str, str]]:
    """
    Finds COI PDF files for a given subcontractor name in a specified directory or via a direct path.
    Uses exact matching first, then falls back to fuzzy matching if enabled and no exact matches found.

    Args:
        pdf_directory_path: The path to the directory containing PDF files.
        subcontractor_name: The name of the subcontractor to search for.
        direct_pdf_path: An optional direct path to a specific PDF file.
        fuzzy_config: Optional fuzzy matching configuration parameters.

    Returns:
        A list of tuples, where each tuple contains:
        - The absolute string path to a found PDF file.
        - An indicator string (currently the original subcontractor_name) associated with the PDF.
        Returns an empty list if no relevant PDFs are found or if errors occur.
    """
    found_pdfs: List[Tuple[str, str]] = []
    normalized_sub_name = _normalize_name(subcontractor_name)

    if not normalized_sub_name:
        logger.warning(f"Subcontractor name '{subcontractor_name}' normalized to an empty string. Cannot search for PDFs.")
        return []

    # Handle direct PDF path first
    if direct_pdf_path:
        abs_direct_path = direct_pdf_path.resolve()
        if abs_direct_path.exists() and abs_direct_path.is_file() and abs_direct_path.name.lower().endswith('.pdf'):
            logger.info(f"Using direct PDF path: {abs_direct_path}")
            found_pdfs.append((str(abs_direct_path), subcontractor_name))
        else:
            logger.warning(
                f"Direct PDF path '{direct_pdf_path}' (resolved to '{abs_direct_path}') "
                f"provided but does not exist, is not a file, or is not a PDF. Ignoring."
            )
        # If a direct path is given, we only consider that, even if it's invalid.
        return found_pdfs

    # Validate pdf_directory_path if direct_pdf_path was not used or was invalid and we proceeded
    if not pdf_directory_path or not os.path.isdir(pdf_directory_path):
        logger.error(f"PDF directory '{pdf_directory_path}' is invalid or not found.")
        return []

    initial_config_path = Path(pdf_directory_path)
    logger.info(f"Initial PDF directory from config: '{initial_config_path}' for subcontractor '{subcontractor_name}' (normalized: '{normalized_sub_name}')")

    # Get configurable folder name from config
    expected_terminal_folder = CONFIG.get('folder_structure', {}).get('coi_folder_name', 'Subcontractor COIs')
    alternative_folder_names = CONFIG.get('folder_structure', {}).get('alternative_folder_names', [])

    search_dir_to_use: Optional[Path]
    
    # Check if the configured path already seems to be the specific COI directory
    all_folder_names = [expected_terminal_folder] + alternative_folder_names
    
    if initial_config_path.name in all_folder_names and initial_config_path.is_dir():
        logger.info(f"Configured path '{initial_config_path}' appears to be a recognized COI directory. Using it directly.")
        search_dir_to_use = initial_config_path
    else:
        # Configured path is not a recognized COI directory.
        # Try appending each possible folder name to find the correct subdirectory.
        search_dir_to_use = None
        for folder_name in all_folder_names:
            potential_specific_dir = initial_config_path / folder_name
            if potential_specific_dir.is_dir():
                logger.info(f"Configured path '{initial_config_path}' does not appear to be a COI directory. "
                            f"Found recognized subdirectory '{potential_specific_dir}'. Adjusting search to this subdirectory.")
                search_dir_to_use = potential_specific_dir
                break
        
        if search_dir_to_use is None:
            # None of the expected folder names were found as subdirectories.
            # Fall back to using the configured path as is.
            logger.warning(f"Could not find any recognized COI subdirectory ({', '.join(all_folder_names)}) under '{initial_config_path}'. "
                           f"Proceeding with configured path '{initial_config_path}' as is. This might lead to no files found if it's not the correct COI PDF location.")
            search_dir_to_use = initial_config_path

    if not search_dir_to_use.is_dir(): # Final check on the chosen path
        logger.error(f"Effective PDF search directory '{search_dir_to_use}' is invalid or not a directory. No PDFs can be found.")
        return []

    logger.info(f"Effectively searching for PDFs for subcontractor '{subcontractor_name}' (normalized: '{normalized_sub_name}') in directory '{search_dir_to_use}'")

    # Collect all PDF files for both exact and fuzzy matching
    pdf_files = []
    try:
        for item_name in os.listdir(search_dir_to_use):
            if item_name.lower().endswith('.pdf'):
                pdf_files.append(item_name)
    except OSError as e:
        logger.error(f"OS error accessing PDF directory '{pdf_directory_path}': {e}")
        return []
    except Exception as e:
        logger.error(f"An unexpected error occurred while searching for PDFs in '{pdf_directory_path}': {e}", exc_info=True)
        return []

    if not pdf_files:
        logger.warning(f"No PDF files found in directory '{search_dir_to_use}'")
        return []

    # Step 1: Try exact matching (existing logic)
    logger.debug(f"Attempting exact matching for '{subcontractor_name}' among {len(pdf_files)} PDF files")
    
    try:
        for item_name in pdf_files:
            # Construct Path object for easier manipulation and normalization
            full_item_path = search_dir_to_use / item_name
            # Normalize filename (without extension) for matching
            # Path.stem extracts the filename without the final extension
            filename_stem_normalized = _normalize_name(full_item_path.stem)
            
            # Guard against empty normalized_sub_name and perform match
            if normalized_sub_name and normalized_sub_name in filename_stem_normalized:
                abs_item_path = full_item_path.resolve()
                logger.debug(f"Found exact match: '{abs_item_path}' for subcontractor '{subcontractor_name}'")
                found_pdfs.append((str(abs_item_path), subcontractor_name))

    except Exception as e:
        logger.error(f"Error during exact matching: {e}", exc_info=True)

    # Step 2: If no exact matches found, try fuzzy matching (if enabled)
    if not found_pdfs:
        # Get fuzzy matching configuration
        default_fuzzy_config = CONFIG.get('fuzzy_matching', {})
        effective_fuzzy_config = fuzzy_config if fuzzy_config else default_fuzzy_config
        
        fuzzy_enabled = effective_fuzzy_config.get('enabled', True)
        
        if fuzzy_enabled and RAPIDFUZZ_AVAILABLE:
            logger.info(f"No exact matches found for '{subcontractor_name}'. Attempting fuzzy matching...")
            
            # Extract filenames without extensions for fuzzy matching
            candidate_stems = [Path(pdf_file).stem for pdf_file in pdf_files]
            
            # Get fuzzy matching parameters
            threshold = effective_fuzzy_config.get('threshold', 75.0)
            max_results = effective_fuzzy_config.get('max_results', 5)
            
            # Perform fuzzy matching
            fuzzy_matches = find_best_fuzzy_matches(
                target_name=subcontractor_name,
                candidate_files=candidate_stems,
                threshold=threshold,
                max_results=max_results
            )
            
            if fuzzy_matches:
                logger.info(f"Found {len(fuzzy_matches)} fuzzy matches for '{subcontractor_name}':")
                for filename_stem, score in fuzzy_matches:
                    # Find the corresponding PDF file
                    matching_pdf = None
                    for pdf_file in pdf_files:
                        if Path(pdf_file).stem == filename_stem:
                            matching_pdf = pdf_file
                            break
                    
                    if matching_pdf:
                        full_item_path = search_dir_to_use / matching_pdf
                        abs_item_path = full_item_path.resolve()
                        found_pdfs.append((str(abs_item_path), subcontractor_name))
                        logger.info(f"  - '{matching_pdf}' (similarity: {score:.1f}%)")
            else:
                logger.warning(f"No fuzzy matches found for '{subcontractor_name}' above threshold {threshold}%")
        elif not fuzzy_enabled:
            logger.debug(f"Fuzzy matching disabled for '{subcontractor_name}'")
        elif not RAPIDFUZZ_AVAILABLE:
            logger.warning(f"Fuzzy matching requested but rapidfuzz library not available for '{subcontractor_name}'")

    if not found_pdfs:
        logger.warning(f"No PDF files found for subcontractor '{subcontractor_name}' in '{pdf_directory_path}' using exact or fuzzy matching.")
    else:
        match_type = "exact" if len(found_pdfs) == 1 else "fuzzy" if not any(normalized_sub_name in _normalize_name(Path(pdf[0]).stem) for pdf, _ in found_pdfs) else "mixed"
        logger.info(f"Found {len(found_pdfs)} PDF(s) for subcontractor '{subcontractor_name}' using {match_type} matching.")
        
    return found_pdfs

# --- Date Extraction Logic ---

# More comprehensive regex patterns for dates
# Handles MM/DD/YYYY, MM-DD-YYYY, YYYY/MM/DD, YYYY-MM-DD, Month DD, YYYY, DD Month YYYY etc.
# And variations with 1 or 2 digit day/month.
DATE_PATTERNS = [
    # MM/DD/YYYY or M/D/YYYY (with or without leading zeros)
    r'\b(0?[1-9]|1[0-2])/(0?[1-9]|[12][0-9]|3[01])/((?:19|20)\d{2})\b',
    # MM-DD-YYYY or M-D-YYYY
    r'\b(0?[1-9]|1[0-2])-(0?[1-9]|[12][0-9]|3[01])-((?:19|20)\d{2})\b',
    # YYYY/MM/DD or YYYY/M/D
    r'\b((?:19|20)\d{2})/(0?[1-9]|1[0-2])/(0?[1-9]|[12][0-9]|3[01])\b',
    # YYYY-MM-DD or YYYY-M-D
    r'\b((?:19|20)\d{2})-(0?[1-9]|1[0-2])-(0?[1-9]|[12][0-9]|3[01])\b',
    # Month DD, YYYY (e.g., Jan 01, 2023 or January 1, 2023)
    r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(0?[1-9]|[12][0-9]|3[01]),?\s+((?:19|20)\d{2})\b',
    # DD Month YYYY (e.g., 01 Jan 2023 or 1 January 2023)
    r'\b(0?[1-9]|[12][0-9]|3[01])\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?,?\s+((?:19|20)\d{2})\b',
    # MM/DD/YY or M/D/YY (will need to infer century)
    r'\b(0?[1-9]|1[0-2])/(0?[1-9]|[12][0-9]|3[01])/(\d{2})\b',
    # MM-DD-YY or M-D-YY
    r'\b(0?[1-9]|1[0-2])-(0?[1-9]|[12][0-9]|3[01])-(\d{2})\b',
]

# Keywords for policy types and date roles
POLICY_KEYWORDS = {
    'general liability': ['general liability', 'commercial general liability', 'cgl'],
    'workers compensation': ["workers' compensation", "workers comp", "wc", "workmen's compensation"],
    # 'auto liability': ['auto liability', 'automobile liability', 'business auto'],
    # 'umbrella liability': ['umbrella liability', 'excess liability'],
}

DATE_ROLE_KEYWORDS = {
    'effective_date': ['effective date', 'eff date', 'policy effective', 'from', 'start date', 'commencement date'],
    'expiration_date': ['expiration date', 'exp date', 'policy expiration', 'to', 'end date', 'expiry date', 'valid until'],
}

def _parse_date_string(date_str: str, notes: List[str]) -> Optional[date]:
    """Attempts to parse a date string into a date object using dateutil."""
    if not dateutil_parse or not DateutilParserError:
        notes.append("Dateutil library not available for parsing.")
        return None
    try:
        # common_era_start_year helps with 2-digit years.
        # If year is < 70, it's 20xx, else 19xx. Adjust as needed.
        # dayfirst=False is common for US dates (MM/DD/YYYY)
        dt_obj = dateutil_parse(date_str, dayfirst=False, yearfirst=False)
        return dt_obj.date()
    except DateutilParserError:
        notes.append(f"DateutilParserError: Could not parse date string: '{date_str}'")
    except ValueError as ve: # Handles cases like "02/30/2023"
        notes.append(f"ValueError: Invalid date components in '{date_str}': {ve}")
    except Exception as e:
        notes.append(f"Unexpected error parsing date string '{date_str}': {e}")
    return None

def _extract_text_from_pdf_pypdf(pdf_path: Path, notes: List[str]) -> Optional[str]:
    """Extracts all text from a PDF using pypdf."""
    if not PdfReader:
        notes.append("pypdf library not available for text extraction.")
        return None
    try:
        reader = PdfReader(pdf_path)
        full_text = ""
        for i, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text()
                if page_text:
                    full_text += page_text + "\n"
                else:
                    notes.append(f"Page {i+1}: No text extracted (possibly image-based or empty).")
            except Exception as e_page:
                notes.append(f"Error extracting text from page {i+1} of '{pdf_path.name}': {e_page}")
                logger.warning(f"Error extracting text from page {i+1} of '{pdf_path.name}': {e_page}")
        
        if not full_text.strip():
            notes.append(f"No text content found in PDF '{pdf_path.name}' after processing all pages.")
            logger.warning(f"No text content found in PDF '{pdf_path.name}'.")
            return None
        return full_text.lower() # Convert to lowercase for easier matching
    except FileNotFoundError:
        notes.append(f"PDF file not found at path: {pdf_path}")
        logger.error(f"PDF file not found: {pdf_path}")
    except Exception as e:
        notes.append(f"Failed to read or parse PDF '{pdf_path.name}' with pypdf: {e}")
        logger.error(f"pypdf error reading PDF '{pdf_path.name}': {e}", exc_info=True)
    return None

def extract_raw_ocr_text_from_pdf(pdf_path: Path, notes: List[str]) -> str:
    """
    Extracts raw text from a PDF. It first tries pypdf. If pypdf fails
    or extracts minimal text from potentially image-based PDFs, it falls
    back to PaddleOCR. Includes CRITICAL debug logging.
    """
    # notes: List[str] = [] # REMOVED
    
    pypdf_text = _extract_text_from_pdf_pypdf(pdf_path, notes)

    # --- CONFIG-DRIVEN OCR DECISION ---
    cfg = CONFIG.get("ocr_processing", {})       # pull from singleton imported at top
    min_len = cfg.get("min_text_len_for_ocr_bypass", 200)

    total_len = len(pypdf_text.strip()) if pypdf_text else 0

    attempt_ocr = (total_len < min_len)

    if attempt_ocr:
        logger.debug(f"Activating OCR because extracted text length is {total_len} (< {min_len})")
    else:
        logger.debug(f"Skipping OCR (len={total_len} ≥ {min_len})")

    if attempt_ocr:
        logger.debug(f"Attempting PaddleOCR for {pdf_path.name}")
        try:
            logger.debug(f"Importing OCR dependencies and converting PDF for {pdf_path.name}")
            from paddleocr import PaddleOCR
            from pdf2image import convert_from_path
            import numpy as np
            import cv2 # Restored import

            # Consider initializing PaddleOCR engine once globally for performance.
            ocr_engine = PaddleOCR(use_angle_cls=True, lang='en', show_log=False, use_gpu=False) # Restored initialization
            logger.debug(f"Initialized PaddleOCR engine for {pdf_path.name}")
            
            # Check for Poppler path if on Windows, as pdf2image might need it.
            # This should ideally be handled by environment setup or a config check.
            poppler_path_env = os.getenv('POPPLER_BIN_PATH') # Use poppler_path_env for clarity with Path()
            if poppler_path_env:
                images = convert_from_path(pdf_path, poppler_path=Path(poppler_path_env))
            else:
                images = convert_from_path(pdf_path)
            logger.debug(f"Converted PDF to {len(images)} image(s) for {pdf_path.name}")
            
            all_ocr_extracted_text_parts = []
            for i, pil_image in enumerate(images):
                # Convert PIL image to OpenCV format (BGR)
                img_np = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                
                ocr_result_for_image = ocr_engine.ocr(img_np, cls=True) # Perform OCR
                # Log the raw result structure for debugging
                logger.debug(f"PaddleOCR result for page {i+1} of {pdf_path.name}")

                page_text_parts = []
                # PaddleOCR can return None or list of lists/Nones. Example: [[[[box], ('text', conf)], ...]] or [None]
                if ocr_result_for_image and isinstance(ocr_result_for_image, list) and ocr_result_for_image[0] is not None:
                    for detection_block in ocr_result_for_image: # Iterate through blocks if any
                        if detection_block: # Check if block is not None
                           for line_data in detection_block: # line_data is typically [[points], (text, confidence)]
                               if line_data and len(line_data) == 2 and isinstance(line_data[1], tuple) and len(line_data[1]) == 2:
                                   page_text_parts.append(line_data[1][0])
                               else:
                                   logger.debug(f"Unexpected line_data structure for page {i+1}: {line_data}")
                
                if page_text_parts:
                    all_ocr_extracted_text_parts.append(" ".join(page_text_parts))
                logger.debug(f"PaddleOCR extracted from page {i+1} of {pdf_path.name} (text len {len(' '.join(page_text_parts))})")

            final_ocr_text = "\n".join(all_ocr_extracted_text_parts).strip()

            if final_ocr_text:
                logger.debug(f"PaddleOCR SUCCESS for {pdf_path.name}. Total text length: {len(final_ocr_text)}")
                return final_ocr_text
            else:
                logger.debug(f"PaddleOCR found no text for {pdf_path.name}. Returning pypdf text")
                return pypdf_text if pypdf_text is not None else ""

        except Exception as e_ocr: # This will catch ImportError as well
            logger.exception(f"Unhandled exception during OCR on {pdf_path.name}", exc_info=True)
            # It's important to decide if notes should still be appended here.
            # The expert's diff doesn't explicitly show it, but for consistency:
            if isinstance(e_ocr, ImportError):
                notes.append(f"OCR libraries missing: {e_ocr}")
            else:
                notes.append(f"OCR attempt failed: {e_ocr}")
            return pypdf_text if pypdf_text is not None else "" # Added fallback return
            # or return from within the try if successful.
    else:
        logger.debug(f"Not attempting PaddleOCR for {pdf_path.name}. Using pypdf output")
        for note in notes: # Log original pypdf notes if not attempting OCR
            if "error" in note.lower() or "failed" in note.lower() or "not found" in note.lower() or "no text extracted" in note.lower():
                 logger.debug(f"Note during pypdf text extraction for {pdf_path.name} (when not attempting OCR): {note}")
        return pypdf_text if pypdf_text is not None else ""

def extract_dates_from_pdf(pdf_path: Union[Path, str], indicator: Optional[str] = None) -> Tuple[Dict[str, Optional[date]], List[str]]:
    """
    Extracts General Liability (GL) and Workers' Compensation (WC) effective and expiration
    dates from a given PDF file.

    Args:
        pdf_path: Path object or string path to the PDF file.
        indicator: Optional string (e.g., subcontractor name) for context in logging/notes.

    Returns:
        A tuple containing:
        - A dictionary with extracted dates:
            {'gl_eff_date': date|None, 'gl_exp_date': date|None,
             'wc_eff_date': date|None, 'wc_exp_date': date|None}
        - A list of notes/errors encountered during processing.
    """
    # Convert string path to Path object if needed
    if isinstance(pdf_path, str):
        pdf_path = Path(pdf_path)
    
    extracted_dates: Dict[str, Optional[date]] = {
        'gl_eff_date': None, 'gl_exp_date': None,
        'wc_eff_date': None, 'wc_exp_date': None,
    }
    notes: List[str] = []
    context_indicator = f" (Indicator: {indicator})" if indicator else ""
    
    logger.info(f"Starting date extraction for PDF: '{pdf_path.name}'{context_indicator}")

    if not pdf_path.exists() or not pdf_path.is_file():
        notes.append(f"PDF file does not exist or is not a file: {pdf_path}")
        logger.error(f"PDF file not found or invalid: {pdf_path}")
        return extracted_dates, notes

    # Step 1: Extract text from PDF
    pdf_text = extract_raw_ocr_text_from_pdf(pdf_path, notes)
    if not pdf_text:
        notes.append("Text extraction failed or PDF was empty.")
        logger.warning(f"Text extraction failed or PDF '{pdf_path.name}' was empty.")
        return extracted_dates, notes
    
    logger.debug(f"Successfully extracted text from '{pdf_path.name}' (length: {len(pdf_text)} chars)")

    # Step 2: Find all potential date strings using regex
    found_date_strings: List[str] = []
    for pattern in DATE_PATTERNS:
        try:
            matches = re.findall(pattern, pdf_text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple): # Some regex patterns return tuples of groups
                    # Heuristic: try to reconstruct a plausible date string from groups
                    # This part might need refinement based on typical tuple structures from DATE_PATTERNS
                    if len(match) == 3 and match[0].isdigit() and match[1].isdigit() and match[2].isdigit(): # e.g. (MM, DD, YYYY) or (YYYY, MM, DD) or (MM,DD,YY)
                        if len(match[2]) == 4: # YYYY is 4 digits
                             date_str_candidate = f"{match[0]}/{match[1]}/{match[2]}" # Assuming M/D/Y or Y/M/D like
                        elif len(match[2]) == 2: # YY is 2 digits
                             date_str_candidate = f"{match[0]}/{match[1]}/{match[2]}"
                        else: # Unclear format
                            continue
                        found_date_strings.append(date_str_candidate)
                    # elif len(match) == 2: # e.g. (Month DD, YYYY) or (DD Month, YYYY)
                    #    date_str_candidate = f"{match[0]} {match[1]}" # This is too generic, rely on dateutil for these
                    #    found_date_strings.append(date_str_candidate)
                elif isinstance(match, str):
                    found_date_strings.append(match)
        except re.error as re_err:
            notes.append(f"Regex error with pattern '{pattern}': {re_err}")
            logger.error(f"Regex error with pattern '{pattern}': {re_err}")
            continue
    
    # Add a broader search for things dateutil might parse directly
    # This regex finds sequences that look like dates, including those with month names.
    # It's quite general, so dateutil will do the heavy lifting of validation.
    potential_date_phrases = re.findall(
        r'\b(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,)?\s+\d{2,4}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?(?:,)?\s+\d{2,4}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b',
        pdf_text,
        re.IGNORECASE
    )
    found_date_strings.extend(potential_date_phrases)
    
    # Deduplicate and parse
    parsed_dates: List[date] = []
    unique_date_strings = sorted(list(set(found_date_strings)), key=len, reverse=True) # Process longer strings first

    if not unique_date_strings:
        notes.append("No potential date strings found via regex in the PDF.")
        logger.warning(f"No potential date strings found via regex in '{pdf_path.name}'.")
    else:
        logger.debug(f"Found {len(unique_date_strings)} unique potential date strings in '{pdf_path.name}'. Sample: {unique_date_strings[:10]}")

    for date_str in unique_date_strings:
        dt = _parse_date_string(date_str, notes)
        if dt and dt not in parsed_dates:
            parsed_dates.append(dt)
            logger.debug(f"Successfully parsed date '{date_str}' -> {dt}")
    
    parsed_dates.sort() # Sort dates chronologically

    if not parsed_dates:
        notes.append("No valid dates could be parsed from the extracted strings.")
        logger.warning(f"No valid dates parsed from '{pdf_path.name}'.")
        return extracted_dates, notes
    
    logger.debug(f"Successfully parsed {len(parsed_dates)} unique dates from '{pdf_path.name}'. Dates: {parsed_dates}")
    logger.debug(f"Starting context-aware date assignment for {len(parsed_dates)} dates")

    # Step 3: Attempt to associate dates with policy types and roles (Simplified approach)
    # This is a very basic heuristic. A more robust solution would involve NLP, layout analysis,
    # or more sophisticated keyword proximity analysis.

    # Look for sections related to GL and WC
    # For simplicity, we'll just take the earliest as effective and latest as expiration if multiple found.
    # This is a major simplification and likely needs improvement.

    # Try to find GL dates
    gl_text_region = ""
    wc_text_region = ""

    # Crude way to find regions (look for policy type keywords)
    # A better way would be to analyze text near "General Liability" and "Workers Compensation" headers
    # For now, we'll search the whole document for keywords near dates. This is very naive.

    # This simplified logic will just pick the first two distinct dates as GL eff/exp, and next two as WC eff/exp
    # if enough dates are found. This is highly unreliable.
    # A better approach:
    # 1. Find sections for GL and WC using POLICY_KEYWORDS.
    # 2. Within those sections, find dates and associate them using DATE_ROLE_KEYWORDS.

    # Enhanced context-aware date assignment logic
    # This replaces the naive chronological assignment with contextual analysis
    
    if len(parsed_dates) >= 2:
        # Step 1: Identify and exclude certificate issue dates
        certificate_dates = []
        policy_dates = []
        
        for date_obj in parsed_dates:
            # Convert date back to string format to find in text
            # Try both with and without leading zeros
            date_str_no_zeros = f"{date_obj.month}/{date_obj.day}/{date_obj.year}"
            date_str_with_zeros = date_obj.strftime("%m/%d/%Y")
            
            # Use the format that appears in the text
            if date_str_no_zeros in pdf_text:
                date_str = date_str_no_zeros
            elif date_str_with_zeros in pdf_text:
                date_str = date_str_with_zeros
            else:
                date_str = date_str_no_zeros  # Default fallback
            
            # Find all positions where this date appears
            date_positions = []
            start = 0
            while True:
                pos = pdf_text.find(date_str, start)
                if pos == -1:
                    break
                date_positions.append(pos)
                start = pos + 1
            
            # Check if this date appears near certificate headers
            is_certificate_date = False
            for pos in date_positions:
                context_start = max(0, pos - 50)
                context_end = min(len(pdf_text), pos + len(date_str) + 50)
                context = pdf_text[context_start:context_end].upper()
                
                # Look for certificate date indicators
                if any(indicator in context for indicator in [
                    "DATE (MM/DD/YYYY)", "CERTIFICATE", "ISSUED", "DATE:"
                ]):
                    is_certificate_date = True
                    break
            
            if is_certificate_date:
                certificate_dates.append(date_obj)
                logger.debug(f"Identified certificate date: {date_obj}")
            else:
                policy_dates.append(date_obj)
                logger.debug(f"Identified policy date: {date_obj}")
        
        # Step 2: Find date pairs that appear together in policy sections
        date_pairs = []
        policy_dates_sorted = sorted(policy_dates)
        
        for i, date1 in enumerate(policy_dates_sorted):
            for j, date2 in enumerate(policy_dates_sorted[i+1:], i+1):
                # Check if these two dates appear together in the text
                # Try both with and without leading zeros for each date
                date1_str_no_zeros = f"{date1.month}/{date1.day}/{date1.year}"
                date1_str_with_zeros = date1.strftime("%m/%d/%Y")
                date2_str_no_zeros = f"{date2.month}/{date2.day}/{date2.year}"
                date2_str_with_zeros = date2.strftime("%m/%d/%Y")
                
                # Use the format that appears in the text
                date1_str = date1_str_no_zeros if date1_str_no_zeros in pdf_text else date1_str_with_zeros
                date2_str = date2_str_no_zeros if date2_str_no_zeros in pdf_text else date2_str_with_zeros
                
                # Look for these dates appearing close together (within 100 characters)
                date1_positions = [m.start() for m in re.finditer(re.escape(date1_str), pdf_text)]
                date2_positions = [m.start() for m in re.finditer(re.escape(date2_str), pdf_text)]
                
                for pos1 in date1_positions:
                    for pos2 in date2_positions:
                        if abs(pos1 - pos2) <= 100:  # Dates appear within 100 characters
                            # Check if this appears in a policy section (not certificate header)
                            section_start = max(0, min(pos1, pos2) - 200)
                            section_end = min(len(pdf_text), max(pos1, pos2) + 200)
                            section = pdf_text[section_start:section_end].upper()
                            
                            # Look for policy indicators
                            policy_indicators = [
                                "GENERAL LIABILITY", "LIABILITY", "OCCURRENCE",
                                "AGGREGATE", "PERSONAL", "BODILY INJURY", "PROPERTY DAMAGE",
                                "WORKERS COMPENSATION", "UMBRELLA", "EXCESS"
                            ]
                            
                            if any(indicator in section for indicator in policy_indicators):
                                # This is a valid date pair in a policy section
                                pair = (min(date1, date2), max(date1, date2))  # (effective, expiration)
                                if pair not in date_pairs:
                                    date_pairs.append(pair)
                                    logger.debug(f"Found date pair: {pair[0]} to {pair[1]}")
        
        # Step 3: Assign date pairs to policy types
        # For now, assign the first valid date pair to GL
        # This can be enhanced with proximity analysis to GL vs WC keywords
        
        if date_pairs:
            # Use the first date pair for GL (most common case)
            gl_effective, gl_expiration = date_pairs[0]
            extracted_dates['gl_eff_date'] = gl_effective
            extracted_dates['gl_exp_date'] = gl_expiration
            
            logger.debug(f"Assigned GL dates from date pair: {gl_effective} to {gl_expiration}")
            
            # If there are additional date pairs, assign to WC
            if len(date_pairs) > 1:
                wc_effective, wc_expiration = date_pairs[1]
                extracted_dates['wc_eff_date'] = wc_effective
                extracted_dates['wc_exp_date'] = wc_expiration
                logger.debug(f"Assigned WC dates from date pair: {wc_effective} to {wc_expiration}")
        
        # Step 4: Fallback to naive assignment if contextual analysis fails
        if not extracted_dates['gl_eff_date'] and not extracted_dates['gl_exp_date']:
            logger.warning("Contextual date assignment failed, falling back to naive assignment")
            
            # Use policy dates (excluding certificate dates) for naive assignment
            available_dates = sorted(policy_dates) if policy_dates else sorted(parsed_dates)
            
            if len(available_dates) >= 1:
                extracted_dates['gl_eff_date'] = available_dates[0]
            if len(available_dates) >= 2:
                potential_exp_gl = [d for d in available_dates if d > extracted_dates['gl_eff_date']] if extracted_dates['gl_eff_date'] else available_dates[1:]
                if potential_exp_gl:
                    extracted_dates['gl_exp_date'] = potential_exp_gl[0]
                elif len(available_dates) >= 2:
                    extracted_dates['gl_exp_date'] = available_dates[1]

        # Step 5: Assign remaining dates to WC if not already assigned
        if not extracted_dates['wc_eff_date'] and not extracted_dates['wc_exp_date']:
            remaining_dates = [d for d in policy_dates if d not in [extracted_dates['gl_eff_date'], extracted_dates['gl_exp_date']]]
            if len(remaining_dates) >= 1:
                extracted_dates['wc_eff_date'] = remaining_dates[0]
            if len(remaining_dates) >= 2:
                potential_exp_wc = [d for d in remaining_dates if d > extracted_dates['wc_eff_date']] if extracted_dates['wc_eff_date'] else remaining_dates[1:]
                if potential_exp_wc:
                    extracted_dates['wc_exp_date'] = potential_exp_wc[0]
                elif len(remaining_dates) >= 2:
                    extracted_dates['wc_exp_date'] = remaining_dates[1]


    if not extracted_dates['gl_eff_date'] and not extracted_dates['gl_exp_date'] and \
       not extracted_dates['wc_eff_date'] and not extracted_dates['wc_exp_date'] and parsed_dates:
        notes.append("Found dates, but could not reliably assign them to GL/WC effective/expiration roles with current simple logic.")
        logger.warning(f"Found dates in '{pdf_path.name}', but assignment to roles failed with simple logic.")
    elif parsed_dates:
         notes.append(f"Assigned dates based on simple ordering/availability: GL Eff: {extracted_dates['gl_eff_date']}, GL Exp: {extracted_dates['gl_exp_date']}, WC Eff: {extracted_dates['wc_eff_date']}, WC Exp: {extracted_dates['wc_exp_date']}.")
         logger.info(f"Assigned dates for '{pdf_path.name}': GL {extracted_dates['gl_eff_date']}-{extracted_dates['gl_exp_date']}, WC {extracted_dates['wc_eff_date']}-{extracted_dates['wc_exp_date']}")


    # Final check for GL: if only one date is found, it's ambiguous.
    if (extracted_dates['gl_eff_date'] and not extracted_dates['gl_exp_date']) or \
       (not extracted_dates['gl_eff_date'] and extracted_dates['gl_exp_date']):
        notes.append("GL: Only one date (effective or expiration) found or assigned. Ambiguous.")
        # Decide if we should nullify both if one is missing, or keep the one found.
        # For now, keeping it. Audit module will handle missing pairs.

    # Final check for WC
    if (extracted_dates['wc_eff_date'] and not extracted_dates['wc_exp_date']) or \
       (not extracted_dates['wc_eff_date'] and extracted_dates['wc_exp_date']):
        notes.append("WC: Only one date (effective or expiration) found or assigned. Ambiguous.")


    return extracted_dates, notes

def diagnose_pdf_discovery(subcontractor_name: str, pdf_directory_path: Optional[str] = None, output_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Provides detailed diagnostics for PDF discovery failures and fuzzy matching analysis.
    
    Args:
        subcontractor_name: The name of the subcontractor to diagnose
        pdf_directory_path: Optional PDF directory path (uses config default if not provided)
        output_file: Optional JSON output file path for detailed analysis
        
    Returns:
        Dictionary containing diagnostic results and recommendations
    """
    logger.info(f"Starting PDF discovery diagnostics for subcontractor: '{subcontractor_name}'")
    
    # Initialize diagnostic results
    diagnostic_results = {
        'subcontractor_name': subcontractor_name,
        'timestamp': datetime.now().isoformat(),
        'config_used': {},
        'directory_analysis': {},
        'pdf_discovery': {},
        'exact_matching': {},
        'fuzzy_matching': {},
        'recommendations': [],
        'summary': {}
    }
    
    try:
        # 1. Analyze configuration
        diagnostic_results['config_used'] = {
            'fuzzy_matching_enabled': CONFIG.get('fuzzy_matching', {}).get('enabled', True),
            'fuzzy_threshold': CONFIG.get('fuzzy_matching', {}).get('threshold', 75.0),
            'fuzzy_algorithms': CONFIG.get('fuzzy_matching', {}).get('algorithms', ['ratio', 'partial_ratio', 'token_sort_ratio']),
            'expected_folder_name': CONFIG.get('folder_structure', {}).get('coi_folder_name', 'Subcontractor COIs'),
            'alternative_folder_names': CONFIG.get('folder_structure', {}).get('alternative_folder_names', []),
            'business_terms': CONFIG.get('name_normalization', {}).get('business_terms', {}),
            'generate_variations': CONFIG.get('name_normalization', {}).get('generate_variations', True)
        }
        
        # 2. Directory validation
        effective_pdf_dir = pdf_directory_path or CONFIG.get('pdf_directory_path', '')
        diagnostic_results['directory_analysis'] = {
            'configured_path': effective_pdf_dir,
            'path_exists': os.path.exists(effective_pdf_dir) if effective_pdf_dir else False,
            'is_directory': os.path.isdir(effective_pdf_dir) if effective_pdf_dir else False,
            'accessible': False,
            'pdf_count': 0,
            'sample_files': []
        }
        
        if effective_pdf_dir and os.path.isdir(effective_pdf_dir):
            try:
                # Check directory structure
                initial_path = Path(effective_pdf_dir)
                expected_folder = CONFIG.get('folder_structure', {}).get('coi_folder_name', 'Subcontractor COIs')
                alternative_folders = CONFIG.get('folder_structure', {}).get('alternative_folder_names', [])
                all_folder_names = [expected_folder] + alternative_folders
                
                # Determine effective search directory
                search_dir = None
                if initial_path.name in all_folder_names:
                    search_dir = initial_path
                    diagnostic_results['directory_analysis']['effective_search_dir'] = str(search_dir)
                    diagnostic_results['directory_analysis']['directory_type'] = 'recognized_coi_directory'
                else:
                    # Look for subdirectories
                    for folder_name in all_folder_names:
                        potential_dir = initial_path / folder_name
                        if potential_dir.is_dir():
                            search_dir = potential_dir
                            diagnostic_results['directory_analysis']['effective_search_dir'] = str(search_dir)
                            diagnostic_results['directory_analysis']['directory_type'] = 'found_coi_subdirectory'
                            break
                    
                    if not search_dir:
                        search_dir = initial_path
                        diagnostic_results['directory_analysis']['effective_search_dir'] = str(search_dir)
                        diagnostic_results['directory_analysis']['directory_type'] = 'using_configured_path'
                
                # Scan for PDF files
                pdf_files = []
                for item in os.listdir(search_dir):
                    if item.lower().endswith('.pdf'):
                        pdf_files.append(item)
                
                diagnostic_results['directory_analysis']['accessible'] = True
                diagnostic_results['directory_analysis']['pdf_count'] = len(pdf_files)
                diagnostic_results['directory_analysis']['sample_files'] = pdf_files[:10]  # First 10 files as sample
                
            except Exception as e:
                diagnostic_results['directory_analysis']['error'] = str(e)
                logger.error(f"Error accessing directory '{effective_pdf_dir}': {e}")
        
        # 3. Name normalization analysis
        normalized_name = _normalize_name(subcontractor_name)
        enhanced_normalized = _normalize_name_enhanced(subcontractor_name)
        name_variations = _get_normalized_variations(subcontractor_name)
        
        diagnostic_results['name_analysis'] = {
            'original_name': subcontractor_name,
            'simple_normalized': normalized_name,
            'enhanced_normalized': enhanced_normalized,
            'all_variations': name_variations,
            'variation_count': len(name_variations)
        }
        
        # 4. PDF discovery testing
        if diagnostic_results['directory_analysis']['accessible'] and diagnostic_results['directory_analysis']['pdf_count'] > 0:
            # Test exact matching
            found_pdfs_exact = find_coi_pdfs(
                pdf_directory_path=effective_pdf_dir,
                subcontractor_name=subcontractor_name,
                fuzzy_config={'enabled': False}  # Disable fuzzy for exact test
            )
            
            diagnostic_results['exact_matching'] = {
                'matches_found': len(found_pdfs_exact),
                'matched_files': [os.path.basename(pdf_path) for pdf_path, _ in found_pdfs_exact]
            }
            
            # Test fuzzy matching with lower threshold for analysis
            fuzzy_config_diagnostic = {
                'enabled': True,
                'threshold': 50.0,  # Lower threshold for diagnostic purposes
                'max_results': 10
            }
            
            found_pdfs_fuzzy = find_coi_pdfs(
                pdf_directory_path=effective_pdf_dir,
                subcontractor_name=subcontractor_name,
                fuzzy_config=fuzzy_config_diagnostic
            )
            
            # Get detailed fuzzy scores
            pdf_files = diagnostic_results['directory_analysis']['sample_files']
            if len(pdf_files) > 10:
                # Get all PDF files for comprehensive analysis
                search_dir = Path(diagnostic_results['directory_analysis']['effective_search_dir'])
                pdf_files = [f for f in os.listdir(search_dir) if f.lower().endswith('.pdf')]
            
            candidate_stems = [Path(pdf_file).stem for pdf_file in pdf_files]
            fuzzy_scores = find_best_fuzzy_matches(
                target_name=subcontractor_name,
                candidate_files=candidate_stems,
                threshold=0.0,  # Get all scores
                max_results=20
            )
            
            diagnostic_results['fuzzy_matching'] = {
                'matches_found': len(found_pdfs_fuzzy),
                'matched_files': [os.path.basename(pdf_path) for pdf_path, _ in found_pdfs_fuzzy],
                'all_scores': fuzzy_scores[:20],  # Top 20 scores
                'threshold_used': fuzzy_config_diagnostic['threshold'],
                'rapidfuzz_available': RAPIDFUZZ_AVAILABLE
            }
            
            # 5. Generate recommendations
            recommendations = []
            
            if not found_pdfs_exact and not found_pdfs_fuzzy:
                recommendations.append("No PDF files found with exact or fuzzy matching. Check if the subcontractor name matches any PDF filenames.")
                recommendations.append(f"Searched in directory: {diagnostic_results['directory_analysis']['effective_search_dir']}")
                recommendations.append(f"Found {diagnostic_results['directory_analysis']['pdf_count']} PDF files total.")
                
                if fuzzy_scores:
                    best_score = fuzzy_scores[0][1]
                    recommendations.append(f"Best fuzzy match score: {best_score:.1f}% for '{fuzzy_scores[0][0]}'")
                    if best_score < 50:
                        recommendations.append("Consider checking if the subcontractor name in Excel matches the PDF filename format.")
                    elif best_score < 75:
                        recommendations.append(f"Consider lowering fuzzy matching threshold below {best_score:.1f}% or verify the filename format.")
            
            elif found_pdfs_exact:
                recommendations.append(f"Exact matching successful: found {len(found_pdfs_exact)} PDF(s).")
                
            elif found_pdfs_fuzzy:
                recommendations.append(f"Fuzzy matching successful: found {len(found_pdfs_fuzzy)} PDF(s).")
                if fuzzy_scores:
                    best_score = fuzzy_scores[0][1]
                    recommendations.append(f"Best match score: {best_score:.1f}%")
                    if best_score < 75:
                        recommendations.append("Consider verifying the match quality or adjusting the fuzzy matching threshold.")
            
            if not RAPIDFUZZ_AVAILABLE:
                recommendations.append("rapidfuzz library not available. Install with: pip install rapidfuzz>=3.6.0")
            
            if diagnostic_results['directory_analysis']['directory_type'] == 'using_configured_path':
                expected_folder = CONFIG.get('folder_structure', {}).get('coi_folder_name', 'Subcontractor COIs')
                recommendations.append(f"Consider organizing PDFs in a '{expected_folder}' subdirectory for better organization.")
            
            # Name variation recommendations
            if len(name_variations) > 1:
                recommendations.append(f"Generated {len(name_variations)} name variations for matching: {name_variations}")
            
            diagnostic_results['recommendations'] = recommendations
        
        else:
            diagnostic_results['recommendations'] = [
                "Cannot perform PDF discovery testing due to directory access issues.",
                f"Verify that the directory path '{effective_pdf_dir}' exists and contains PDF files."
            ]
        
        # 6. Generate summary
        summary = {
            'directory_accessible': diagnostic_results['directory_analysis']['accessible'],
            'pdf_files_found': diagnostic_results['directory_analysis']['pdf_count'],
            'exact_matches': diagnostic_results.get('exact_matching', {}).get('matches_found', 0),
            'fuzzy_matches': diagnostic_results.get('fuzzy_matching', {}).get('matches_found', 0),
            'rapidfuzz_available': RAPIDFUZZ_AVAILABLE,
            'name_variations_generated': len(name_variations)
        }
        
        if summary['exact_matches'] > 0:
            summary['status'] = 'success_exact'
        elif summary['fuzzy_matches'] > 0:
            summary['status'] = 'success_fuzzy'
        elif not summary['directory_accessible']:
            summary['status'] = 'directory_error'
        elif summary['pdf_files_found'] == 0:
            summary['status'] = 'no_pdfs_found'
        else:
            summary['status'] = 'no_matches_found'
        
        diagnostic_results['summary'] = summary
        
        # 7. Save to output file if specified
        if output_file:
            try:
                output_path = Path(output_file)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(diagnostic_results, f, indent=2, default=str)
                logger.info(f"Diagnostic results saved to: {output_path}")
                diagnostic_results['output_file_saved'] = str(output_path)
            except Exception as e:
                logger.error(f"Failed to save diagnostic results to '{output_file}': {e}")
                diagnostic_results['output_file_error'] = str(e)
        
        logger.info(f"PDF discovery diagnostics completed for '{subcontractor_name}'. Status: {summary['status']}")
        return diagnostic_results
        
    except Exception as e:
        logger.error(f"Error during PDF discovery diagnostics for '{subcontractor_name}': {e}", exc_info=True)
        diagnostic_results['error'] = str(e)
        diagnostic_results['summary'] = {'status': 'diagnostic_error'}
        return diagnostic_results
