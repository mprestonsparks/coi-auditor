import os
import platform # To check OS if needed, though PATH modification is generally safe

# Define the directory containing tesseract.exe
tesseract_executable_dir = r"C:\Program Files\Tesseract-OCR" # User confirmed this path

# Add Tesseract directory to PATH if not already present
# This is crucial for pytesseract to find tesseract.exe on some systems/environments
current_path = os.environ.get("PATH", "")
if tesseract_executable_dir not in current_path.split(os.pathsep):
    os.environ["PATH"] = current_path + os.pathsep + tesseract_executable_dir

import pytesseract # Import pytesseract AFTER PATH modification
"""Handles finding COI PDFs and extracting relevant dates."""

import pdfplumber
from pdfminer.pdfparser import PDFSyntaxError
import os
import re
from datetime import datetime, date, timedelta
import logging
from difflib import SequenceMatcher
from dateutil.parser import parse as dateutil_parse, ParserError
import numpy as np 
from collections import defaultdict 
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
import warnings
from thefuzz import fuzz 
import cv2 
from skimage.transform import rotate as skimage_rotate 
from skimage.color import rgb2gray 
from skimage.filters import threshold_otsu 
from scipy.signal import find_peaks # For robust valley detection


warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    message=r"CropBox missing from /Page, defaulting to MediaBox",
    module=r"^pdfplumber\."
)
from .config import load_config
from .ml_table_detector import initialize_ml_model, detect_tables_on_page_image 

APP_CONFIG = load_config()

try:
    initialize_ml_model()
    logging.info("Successfully initialized ML table detection model.")
except Exception as e:
    logging.error(f"Failed to initialize ML table detection model during pdf_parser import: {e}", exc_info=True)

MIN_SIMILARITY_SCORE = APP_CONFIG.get('min_similarity_score', 0.7) 
HEADER_SIMILARITY_THRESHOLD = APP_CONFIG.get('fuzzy_matching', {}).get('header_similarity_threshold', 0.88)

OCR_PREPROCESSING_CONFIG = APP_CONFIG.get('ocr_preprocessing', {})
ENABLE_DESKEW = OCR_PREPROCESSING_CONFIG.get('enable_deskew', True)
ENABLE_ADAPTIVE_BINARIZATION = OCR_PREPROCESSING_CONFIG.get('enable_adaptive_binarization', True)
ADAPTIVE_THRESH_BLOCK_SIZE = OCR_PREPROCESSING_CONFIG.get('adaptive_thresh_block_size', 11)
ADAPTIVE_THRESH_C = OCR_PREPROCESSING_CONFIG.get('adaptive_thresh_C', 2)

logging.info(f"PDF Parser using Header Similarity Threshold: {HEADER_SIMILARITY_THRESHOLD*100:.1f}%")
logging.info(f"OCR Preprocessing: Deskew Enabled={ENABLE_DESKEW}, Adaptive Binarization Enabled={ENABLE_ADAPTIVE_BINARIZATION}")
if ENABLE_ADAPTIVE_BINARIZATION:
    logging.info(f"Adaptive Binarization Params: BlockSize={ADAPTIVE_THRESH_BLOCK_SIZE}, C={ADAPTIVE_THRESH_C}")

BROAD_DATE_REGEX = APP_CONFIG.get('broad_date_regex', r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b') 

GL_KEYWORDS = APP_CONFIG.get('policy_section_keywords', {}).get('general_liability', ["general liability", "commercial general liability"])
WC_KEYWORDS = APP_CONFIG.get('policy_section_keywords', {}).get('workers_compensation', ["workers compensation", "workers' compensation"])
AUTO_KEYWORDS = APP_CONFIG.get('policy_section_keywords', {}).get('automobile_liability', ["automobile liability"])
UMBRELLA_KEYWORDS = APP_CONFIG.get('policy_section_keywords', {}).get('umbrella_liability', ["umbrella liability"])

EFFECTIVE_DATE_KEYWORDS = [kw.lower() for kw in APP_CONFIG.get('date_column_header_keywords', {}).get('effective_date', ["policy eff", "eff date"])]
EXPIRATION_DATE_KEYWORDS = [kw.lower() for kw in APP_CONFIG.get('date_column_header_keywords', {}).get('expiration_date', ["policy exp", "exp date"])]
POLICY_NUMBER_COLUMN_KEYWORDS = [kw.lower() for kw in APP_CONFIG.get('coi_specific_keywords', {}).get('policy_number_column', ["POLICY NUMBER", "POL NO.", "POLICY #"])]

COI_DATE_LABEL_KEYWORDS = APP_CONFIG.get('coi_specific_keywords', {}).get('coi_date_label', ["DATE", "DATE (MM/DD/YYYY)"])
INSURED_SECTION_HEADER_KEYWORDS = APP_CONFIG.get('coi_specific_keywords', {}).get('insured_section_header', ["INSURED"])

ALL_REQUIRED_FIELDS = [
    "coi_date", "insured_name", "insured_address",
    "gl_policy_number", "gl_eff_date", "gl_exp_date",
    "wc_policy_number", "wc_eff_date", "wc_exp_date",
]

def normalize_name(name):
    import re
    if not name: return ""
    name = name.lower()
    name = re.sub(r'[\-.,&]', '', name)
    name = re.sub(r'\s+', '', name)
    return name

def extract_pdf_stem_and_date(filename):
    base = os.path.splitext(filename)[0]
    if '_GL_' in base: base = base.split('_GL_')[0]
    elif '_WC_' in base: base = base.split('_WC_')[0]
    base_parts = base.rsplit('_', 1)
    date_part = None
    if len(base_parts) == 2 and re.match(r'\d{4}-\d{2}-\d{2}', base_parts[1]):
        date_part = base_parts[1]
        base = base_parts[0]
    return base, date_part

def parse_date_from_part(date_str):
    try: return datetime.strptime(date_str, "%Y-%m-%d")
    except Exception: return None

def find_coi_pdfs(pdf_dir: str, subcontractor_name: str, direct_pdf_path: Optional[Path] = None) -> List[Tuple[str, Optional[str]]]:
    if direct_pdf_path:
        logging.info(f"[find_coi_pdfs] Using direct PDF path: {direct_pdf_path} for subcontractor '{subcontractor_name}' (similarity search bypassed).")
        if not direct_pdf_path.is_file() or not str(direct_pdf_path).lower().endswith('.pdf'):
            logging.warning(f"[find_coi_pdfs] Direct PDF path '{direct_pdf_path}' is not a valid PDF file.")
            return []
        filename = direct_pdf_path.name
        indicator = None
        if '_GL_' in filename: indicator = 'GL'
        elif '_WC_' in filename: indicator = 'WC'
        logging.info(f"[find_coi_pdfs] Selected direct PDF '{filename}' with indicator '{indicator}' for subcontractor '{subcontractor_name}'.")
        return [(str(direct_pdf_path), indicator)]

    found_pdfs = []
    normalized_sub_name = normalize_name(subcontractor_name)
    logging.debug(f"[find_coi_pdfs] Normalized subcontractor name: '{normalized_sub_name}' for directory search in '{pdf_dir}'.")
    if not normalized_sub_name:
        logging.warning(f"Attempted to find PDFs for an empty subcontractor name during directory search in '{pdf_dir}'.")
        return []
    if not os.path.isdir(pdf_dir):
        logging.error(f"PDF directory not found or is not a directory: {pdf_dir}")
        return []

    best_score = 0.0
    best_pdf = None
    best_indicator = None
    best_date = None 
    for filename in os.listdir(pdf_dir):
        if not filename.lower().endswith('.pdf'): continue
        stem, date_part = extract_pdf_stem_and_date(filename)
        normalized_stem = normalize_name(stem)
        score = SequenceMatcher(None, normalized_sub_name, normalized_stem).ratio()
        logging.debug(f"[find_coi_pdfs] Evaluating PDF: '{filename}' | Normalized stem: '{normalized_stem}' | Score: {score:.3f} | Date: {date_part}")
        indicator = None
        if '_GL_' in filename: indicator = 'GL'
        elif '_WC_' in filename: indicator = 'WC'
        pdf_date_obj = parse_date_from_part(date_part) # This can be None
        # Ensure comparison is between datetime objects or use datetime.min as a fallback for None
        pdf_date_to_compare = pdf_date_obj if pdf_date_obj is not None else datetime.min
        best_date_to_compare = best_date if best_date is not None else datetime.min

        if score > best_score or \
           (score == best_score and pdf_date_to_compare > best_date_to_compare):
            best_score = score
            best_pdf = filename
            best_indicator = indicator
            best_date = pdf_date_obj # Use the object that can be None
    if best_pdf and best_score >= MIN_SIMILARITY_SCORE:
        best_pdf_path = os.path.join(pdf_dir, best_pdf)
        found_pdfs.append((best_pdf_path, best_indicator))
        logging.info(f"[find_coi_pdfs] Selected PDF '{best_pdf}' for '{subcontractor_name}' from directory '{pdf_dir}' (score: {best_score:.3f}, date: {best_date.strftime('%Y-%m-%d') if best_date and best_date != datetime.min else 'N/A'})")
    else:
        logging.warning(f"[find_coi_pdfs] No PDF for '{subcontractor_name}' in directory '{pdf_dir}' met minimum similarity ({MIN_SIMILARITY_SCORE}); best score was {best_score:.3f}")
    return found_pdfs

def parse_date(date_str, is_candidate_phase=False):
    logging.debug(f"[parse_date] Input: '{date_str}', is_candidate_phase: {is_candidate_phase}")
    if not date_str or not isinstance(date_str, str):
        logging.debug(f"[parse_date] Input '{date_str}' is None or not a string. Returning None.")
        return None
    parsed_dt = None
    original_date_str = date_str 
    if is_candidate_phase:
        match_broad = re.match(BROAD_DATE_REGEX, date_str, re.IGNORECASE)
        logging.debug(f"[parse_date] Candidate phase: Broad regex ('{BROAD_DATE_REGEX}') match for '{date_str}': {bool(match_broad)}")
        if not match_broad:
            logging.debug(f"[parse_date] Candidate phase: No broad regex match. Returning None.")
            return None 
    try:
        cleaned_date_str = re.sub(r'[^\w\s/-]', '', date_str.strip()).strip()
        logging.debug(f"[parse_date] Cleaned date string: '{cleaned_date_str}' from '{date_str}'")
        if not cleaned_date_str:
            logging.debug(f"[parse_date] Cleaned date string is empty. Returning None.")
            return None
        parsed_dt = dateutil_parse(cleaned_date_str)
        logging.debug(f"[parse_date] dateutil_parse result for '{cleaned_date_str}': {parsed_dt}")
    except (ParserError, ValueError, OverflowError) as e:
        # Use original_date_str for logging here as cleaned_date_str might not be bound if error occurred before its assignment
        logging.debug(f"[parse_date] dateutil.parser.parse failed for '{original_date_str}': {e}")
        if not is_candidate_phase:
            match = re.search(BROAD_DATE_REGEX, original_date_str, re.IGNORECASE)
            logging.debug(f"[parse_date] Fallback broad regex search for '{original_date_str}': {bool(match)}")
            if match:
                date_str_from_regex = match.group(0)
                logging.debug(f"[parse_date] Fallback regex matched: '{date_str_from_regex}'")
                try:
                    parsed_dt = dateutil_parse(date_str_from_regex)
                    logging.debug(f"[parse_date] Fallback dateutil_parse result for '{date_str_from_regex}': {parsed_dt}")
                except (ParserError, ValueError, OverflowError) as e_fallback:
                    logging.debug(f"[parse_date] Fallback parsing of regex match '{date_str_from_regex}' also failed: {e_fallback}")
                    parsed_dt = None 
            else:
                parsed_dt = None 
        else:
            logging.debug(f"[parse_date] Candidate phase: dateutil parse failed, but broad regex passed. Returning None for now.")
            return None 
    if not parsed_dt:
        if not is_candidate_phase: 
            logging.debug(f"[parse_date] Could not parse date string: '{original_date_str}' using dateutil or broad regex. Returning None.")
        else: 
            logging.debug(f"[parse_date] Candidate phase: Broad regex matched '{original_date_str}', but dateutil parsing failed. Returning None.")
        return None
    try:
        final_date = parsed_dt.date()
        logging.debug(f"[parse_date] Converted to date object: {final_date}")
        years_offset = APP_CONFIG.get('date_plausibility', {}).get('years_offset_from_today', 5)
        current_date = datetime.now().date()
        min_plausible_date = current_date.replace(year=current_date.year - years_offset)
        max_plausible_date = current_date.replace(year=current_date.year + years_offset)
        logging.debug(f"[parse_date] Plausibility range: {min_plausible_date} to {max_plausible_date}")
        if not (min_plausible_date <= final_date <= max_plausible_date):
            logging.debug(f"[parse_date] Parsed date {final_date} for '{original_date_str}' is outside plausible range. Returning None.")
            return None
        if final_date.year < 1900 or final_date.year > datetime.now().year + years_offset + 5: 
             logging.debug(f"[parse_date] Parsed date {final_date} for '{original_date_str}' has an unlikely year ({final_date.year}). Returning None.")
             return None
        logging.debug(f"[parse_date] Successfully parsed '{original_date_str}' to {final_date}. Returning date.")
        return final_date
    except ValueError as e: 
        logging.debug(f"[parse_date] Error during plausibility check or final conversion for '{original_date_str}': {e}. Returning None.")
        return None

def search_text_for_date_candidates(text_block):
    if not text_block or not isinstance(text_block, str): return []
    try:
        matches = re.finditer(BROAD_DATE_REGEX, text_block, re.IGNORECASE)
        found_dates = [match.group(0) for match in matches] 
    except re.error as e:
        logging.error(f"Regex error with BROAD_DATE_REGEX: {e}. Using a default safe pattern.")
        matches = re.finditer(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', text_block, re.IGNORECASE)
        found_dates = [match.group(0) for match in matches]
    return list(dict.fromkeys(found_dates)) 

def get_words_with_bbox(page_obj):
    return page_obj.extract_words(x_tolerance=1, y_tolerance=1, keep_blank_chars=False) 

def find_section_header_roi(page_words, header_keywords_for_section):
    logging.debug(f"[find_section_header_roi] Starting. Keywords: {header_keywords_for_section}. Num page_words: {len(page_words)}")
    if page_words: logging.debug(f"[find_section_header_roi] First 5 page_words: {page_words[:5]}")
    best_match_words = []
    max_keywords_found_in_line = 0
    lines = defaultdict(list)
    for word in page_words: lines[round(word['top'] / 5.0) * 5.0].append(word)
    logging.debug(f"[find_section_header_roi] Grouped page_words into {len(lines)} visual lines.")
    for line_top_coord, line_words_on_visual_line in sorted(lines.items()):
        line_words_on_visual_line.sort(key=lambda w: w['x0']) 
        line_text = " ".join(w['text'] for w in line_words_on_visual_line).lower()
        logging.debug(f"[find_section_header_roi] Processing line at top ~{line_top_coord}: '{line_text[:100]}...'")
        keywords_found_count = 0
        current_match_words_for_this_line = []
        for kw in header_keywords_for_section:
            kw_lower = kw.lower()
            if kw_lower in line_text:
                logging.debug(f"[find_section_header_roi] Keyword '{kw_lower}' found in line '{line_text[:100]}...'")
                keywords_found_count +=1
                for word_obj in line_words_on_visual_line:
                    if kw_lower in word_obj['text'].lower() and word_obj not in current_match_words_for_this_line:
                        current_match_words_for_this_line.append(word_obj)
        if keywords_found_count > 0:
            logging.debug(f"[find_section_header_roi] Line '{line_text[:100]}...' had {keywords_found_count} keywords. Matched words: {[w['text'] for w in current_match_words_for_this_line]}")
            if keywords_found_count > max_keywords_found_in_line:
                max_keywords_found_in_line = keywords_found_count
                best_match_words = current_match_words_for_this_line
                logging.debug(f"[find_section_header_roi] New best match line with {max_keywords_found_in_line} keywords.")
            elif keywords_found_count == max_keywords_found_in_line and len(current_match_words_for_this_line) > len(best_match_words):
                best_match_words = current_match_words_for_this_line
                logging.debug(f"[find_section_header_roi] Updated best match (same keyword count, more words).")
    if not best_match_words:
        logging.debug(f"[find_section_header_roi] No section header found for keywords: {header_keywords_for_section}. Returning None.")
        return None
    x0 = min(w['x0'] for w in best_match_words)
    top = min(w['top'] for w in best_match_words)
    x1 = max(w['x1'] for w in best_match_words)
    bottom = max(w['bottom'] for w in best_match_words)
    found_header_text = " ".join(w['text'] for w in best_match_words)
    found_roi = {'bbox': (x0, top, x1, bottom), 'words': best_match_words, 'text': found_header_text}
    logging.debug(f"[find_section_header_roi] Found section header: '{found_header_text}' with ROI: {found_roi['bbox']}. Returning ROI.")
    return found_roi

def find_column_rois(page_words: List[Dict[str, Any]],
                       search_roi_bbox: Tuple[float, float, float, float],
                       eff_col_keywords: List[str],
                       exp_col_keywords: List[str],
                       pol_num_col_keywords: List[str],
                       context_width: float, 
                       similarity_threshold: float) -> Dict[str, Optional[Dict[str, Any]]]:
    logging.debug(f"[find_column_rois] Starting. Search ROI: {search_roi_bbox}. Context_width: {context_width}. Similarity_threshold: {similarity_threshold}")
    logging.debug(f"[find_column_rois] Eff_keywords: {eff_col_keywords}, Exp_keywords: {exp_col_keywords}, Pol_num_keywords: {pol_num_col_keywords}")
    eff_header_candidates: List[Dict[str, Any]] = []
    exp_header_candidates: List[Dict[str, Any]] = []
    pol_num_header_candidates: List[Dict[str, Any]] = []
    relevant_words_for_headers = [
        w for w in page_words
        if w['bottom'] <= search_roi_bbox[3] and w['top'] >= search_roi_bbox[1] and \
           w['x1'] > search_roi_bbox[0] and w['x0'] < search_roi_bbox[2]
    ]
    logging.debug(f"[find_column_rois] Found {len(relevant_words_for_headers)} relevant words for headers in search ROI. First 5: {relevant_words_for_headers[:5]}")
    lines = defaultdict(list)
    for word in relevant_words_for_headers: lines[round(word['top'] / 5.0) * 5.0].append(word)
    logging.debug(f"[find_column_rois] Grouped relevant_words into {len(lines)} visual lines.")
    for line_top_coord, line_words in sorted(lines.items()):
        line_words.sort(key=lambda w: w['x0'])
        line_text_lower = " ".join(w['text'] for w in line_words).lower()
        logging.debug(f"[find_column_rois] Processing line for column headers at top ~{line_top_coord}: '{line_text_lower[:100]}...'")
        for kw_eff in eff_col_keywords:
            score = fuzz.partial_ratio(kw_eff, line_text_lower) / 100.0 
            if score >= similarity_threshold:
                logging.debug(f"[find_column_rois] Eff keyword '{kw_eff}' fuzzy matched line with score {score:.2f} (threshold {similarity_threshold:.2f}). Line: '{line_text_lower[:60]}...'")
                matched_header_words = [w for w in line_words if kw_eff.split()[0] in w['text'].lower()] 
                if not matched_header_words: matched_header_words = line_words 
                candidate = {'words': matched_header_words, 'text': " ".join(w['text'] for w in matched_header_words), 'x0': min(w['x0'] for w in matched_header_words), 'x1': max(w['x1'] for w in matched_header_words), 'top': min(w['top'] for w in matched_header_words), 'bottom': max(w['bottom'] for w in matched_header_words), 'score': score, 'keyword_matched': kw_eff}
                eff_header_candidates.append(candidate)
                logging.debug(f"[find_column_rois] Added Eff header candidate: {candidate['text']} at { (candidate['x0'], candidate['top'], candidate['x1'], candidate['bottom'])} with score {score:.2f}")
        for kw_exp in exp_col_keywords:
            score = fuzz.partial_ratio(kw_exp, line_text_lower) / 100.0
            if score >= similarity_threshold:
                logging.debug(f"[find_column_rois] Exp keyword '{kw_exp}' fuzzy matched line with score {score:.2f}. Line: '{line_text_lower[:60]}...'")
                matched_header_words = [w for w in line_words if kw_exp.split()[0] in w['text'].lower()]
                if not matched_header_words: matched_header_words = line_words
                candidate = {'words': matched_header_words, 'text': " ".join(w['text'] for w in matched_header_words), 'x0': min(w['x0'] for w in matched_header_words), 'x1': max(w['x1'] for w in matched_header_words), 'top': min(w['top'] for w in matched_header_words), 'bottom': max(w['bottom'] for w in matched_header_words), 'score': score, 'keyword_matched': kw_exp}
                exp_header_candidates.append(candidate)
                logging.debug(f"[find_column_rois] Added Exp header candidate: {candidate['text']} at { (candidate['x0'], candidate['top'], candidate['x1'], candidate['bottom'])} with score {score:.2f}")
        for kw_pol_num in pol_num_col_keywords:
            score = fuzz.partial_ratio(kw_pol_num, line_text_lower) / 100.0
            if score >= similarity_threshold:
                logging.debug(f"[find_column_rois] PolNum keyword '{kw_pol_num}' fuzzy matched line with score {score:.2f}. Line: '{line_text_lower[:60]}...'")
                matched_header_words = [w for w in line_words if kw_pol_num.split()[0] in w['text'].lower()]
                if not matched_header_words: matched_header_words = line_words
                candidate = {'words': matched_header_words, 'text': " ".join(w['text'] for w in matched_header_words), 'x0': min(w['x0'] for w in matched_header_words), 'x1': max(w['x1'] for w in matched_header_words), 'top': min(w['top'] for w in matched_header_words), 'bottom': max(w['bottom'] for w in matched_header_words), 'score': score, 'keyword_matched': kw_pol_num}
                pol_num_header_candidates.append(candidate)
                logging.debug(f"[find_column_rois] Added PolNum header candidate: {candidate['text']} at { (candidate['x0'], candidate['top'], candidate['x1'], candidate['bottom'])} with score {score:.2f}")
    logging.debug(f"[find_column_rois] Found {len(eff_header_candidates)} Eff, {len(exp_header_candidates)} Exp, {len(pol_num_header_candidates)} PolNum header candidates.")
    def get_best_column_info(header_candidates: List[Dict[str, Any]], col_type_name: str, search_roi_bottom: float, current_context_width: float) -> Optional[Dict[str, Any]]:
        if not header_candidates:
            logging.debug(f"[find_column_rois.get_best_column_info] No header candidates for {col_type_name}. Returning None.")
            return None
        header_candidates.sort(key=lambda h: (-h['score'], h['top'], h['x0']))
        candidate_info_log = ""
        if header_candidates: candidate_info_log = ", ".join([f"{{'text': '{c['text'][:30]}...', 'score': {c['score']:.2f}}}" for c in header_candidates[:3]])
        logging.debug(f"[find_column_rois.get_best_column_info] Sorted {col_type_name} header_candidates (best first, up to 3 shown): [{candidate_info_log}]")
        best_header = header_candidates[0] 
        logging.debug(f"[find_column_rois.get_best_column_info] Best header for {col_type_name}: '{best_header['text']}' at {(best_header['x0'], best_header['top'], best_header['x1'], best_header['bottom'])} with score {best_header['score']:.2f} (Keyword: '{best_header['keyword_matched']}')")
        header_x0, header_top, header_x1, header_bottom = best_header['x0'], best_header['top'], best_header['x1'], best_header['bottom']
        col_width_buffer = APP_CONFIG.get('date_column_width_buffer', 20) 
        col_roi_x0 = max(search_roi_bbox[0], header_x0 - col_width_buffer)
        estimated_data_width = (header_x1 - header_x0) * 1.5 + 30 
        col_roi_x1 = min(search_roi_bbox[2], header_x1 + col_width_buffer + estimated_data_width / 3) 
        col_roi_x1 = min(col_roi_x1, search_roi_bbox[0] + current_context_width) 
        col_roi_top = header_bottom + APP_CONFIG.get('date_column_top_offset_from_header', 2) 
        col_roi_bottom = search_roi_bottom 
        column_info = {'bbox': (col_roi_x0, col_roi_top, col_roi_x1, col_roi_bottom), 'header_y_center': (header_top + header_bottom) / 2, 'header_text': best_header['text'], 'header_bbox': (header_x0, header_top, header_x1, header_bottom), 'score': best_header['score'], 'keyword_matched': best_header['keyword_matched']}
        logging.debug(f"[find_column_rois.get_best_column_info] Determined {col_type_name} column ROI: {column_info['bbox']}, Header text: '{column_info['header_text']}', Header BBox: {column_info['header_bbox']}, Score: {column_info['score']:.2f}")
        return column_info
    search_roi_actual_bottom = search_roi_bbox[3]
    eff_col_info = get_best_column_info(eff_header_candidates, "effective", search_roi_actual_bottom, context_width)
    exp_col_info = get_best_column_info(exp_header_candidates, "expiration", search_roi_actual_bottom, context_width)
    pol_num_col_info = get_best_column_info(pol_num_header_candidates, "policy_number", search_roi_actual_bottom, context_width)
    found_columns = []
    if pol_num_col_info: found_columns.append({'type': 'policy_number', 'info': pol_num_col_info})
    if eff_col_info: found_columns.append({'type': 'effective', 'info': eff_col_info})
    if exp_col_info: found_columns.append({'type': 'expiration', 'info': exp_col_info})
    if len(found_columns) > 1:
        found_columns.sort(key=lambda x: x['info']['header_bbox'][0]) 
        log_msg_spatial_order = "Tentative spatial order (left-to-right): " + ", ".join([f"{col['type']} (x0: {col['info']['header_bbox'][0]:.1f}, score: {col['info']['score']:.2f})" for col in found_columns])
        logging.debug(f"[find_column_rois] {log_msg_spatial_order}")
        if eff_col_info and exp_col_info and eff_col_info['header_bbox'][0] > exp_col_info['header_bbox'][0]:
            logging.warning(f"[find_column_rois] Spatial conflict: Effective date column (x0={eff_col_info['header_bbox'][0]}) appears to be to the right of Expiration column (x0={exp_col_info['header_bbox'][0]}). This might indicate a misidentification.")
    result = {'effective_column': eff_col_info, 'expiration_column': exp_col_info, 'policy_number_column': pol_num_col_info}
    logging.debug(f"[find_column_rois] Returning column infos. Eff found: {bool(eff_col_info)}, Exp found: {bool(exp_col_info)}, PolNum found: {bool(pol_num_col_info)}")
    return result

def generate_date_candidates_in_roi(page_words, column_roi, column_type_name_for_logging="date"):
    logging.debug(f"[generate_date_candidates_in_roi] Starting for {column_type_name_for_logging} column. ROI: {column_roi}")
    candidates = []
    if not column_roi:
        logging.debug(f"[generate_date_candidates_in_roi] Cannot generate candidates for {column_type_name_for_logging} as column_roi is None. Returning empty list.")
        return candidates
    words_in_column = [w for w in page_words if max(w['x0'], column_roi[0]) < min(w['x1'], column_roi[2]) and max(w['top'], column_roi[1]) < min(w['bottom'], column_roi[3])]
    logging.debug(f"[generate_date_candidates_in_roi] Found {len(words_in_column)} words in column ROI {column_roi}. First 5: {[{'text': w['text'], 'x0':w['x0'], 'top':w['top']} for w in words_in_column[:5]]}")
    words_in_column.sort(key=lambda w: (w['top'], w['x0']))
    current_line_words = []
    last_word_bottom = 0
    line_y_tolerance = APP_CONFIG.get('date_candidate_line_y_tolerance', 5) 
    max_word_spacing = APP_CONFIG.get('date_candidate_max_word_spacing', 10) 
    logging.debug(f"[generate_date_candidates_in_roi] Grouping words into lines. Line_y_tolerance: {line_y_tolerance}, Max_word_spacing: {max_word_spacing}")
    for word_obj in words_in_column:
        if not current_line_words or (abs(word_obj['top'] - current_line_words[0]['top']) < line_y_tolerance and word_obj['x0'] - current_line_words[-1]['x1'] < max_word_spacing): 
            current_line_words.append(word_obj)
        else:
            if current_line_words:
                line_text = " ".join(w['text'] for w in current_line_words)
                logging.debug(f"[generate_date_candidates_in_roi] Processing assembled line text: '{line_text}'")
                is_broad_match = parse_date(line_text, is_candidate_phase=True) is not None 
                logging.debug(f"[generate_date_candidates_in_roi] Broad parse_date for '{line_text}' (candidate phase): {is_broad_match}")
                if is_broad_match: 
                    final_parsed_date = parse_date(line_text, is_candidate_phase=False) 
                    logging.debug(f"[generate_date_candidates_in_roi] Strict parse_date for '{line_text}': {final_parsed_date}")
                    if final_parsed_date:
                        bbox = (min(w['x0'] for w in current_line_words), min(w['top'] for w in current_line_words), max(w['x1'] for w in current_line_words), max(w['bottom'] for w in current_line_words))
                        candidate_data = {'text': line_text, 'bbox': bbox, 'parsed_date': final_parsed_date, 'y_center': (bbox[1] + bbox[3]) / 2, 'x_center': (bbox[0] + bbox[2]) / 2}
                        candidates.append(candidate_data)
                        logging.debug(f"[generate_date_candidates_in_roi] Added candidate from line: {candidate_data}")
            current_line_words = [word_obj] 
        last_word_bottom = max(last_word_bottom, word_obj['bottom']) 
    if current_line_words:
        line_text = " ".join(w['text'] for w in current_line_words)
        logging.debug(f"[generate_date_candidates_in_roi] Processing last accumulated line text: '{line_text}'")
        is_broad_match_last = parse_date(line_text, is_candidate_phase=True) is not None
        logging.debug(f"[generate_date_candidates_in_roi] Broad parse_date for last line '{line_text}' (candidate phase): {is_broad_match_last}")
        if is_broad_match_last:
            final_parsed_date = parse_date(line_text, is_candidate_phase=False)
            logging.debug(f"[generate_date_candidates_in_roi] Strict parse_date for last line '{line_text}': {final_parsed_date}")
            if final_parsed_date:
                bbox = (min(w['x0'] for w in current_line_words), min(w['top'] for w in current_line_words), max(w['x1'] for w in current_line_words), max(w['bottom'] for w in current_line_words))
                candidate_data = {'text': line_text, 'bbox': bbox, 'parsed_date': final_parsed_date, 'y_center': (bbox[1] + bbox[3]) / 2, 'x_center': (bbox[0] + bbox[2]) / 2}
                candidates.append(candidate_data)
                logging.debug(f"[generate_date_candidates_in_roi] Added candidate from last line: {candidate_data}")
    if not candidates or len(candidates) < 2 : 
        logging.debug(f"[generate_date_candidates_in_roi] Fallback: Line grouping yielded {len(candidates)} candidates. Checking individual words.")
        for word_obj in words_in_column:
            word_text = word_obj['text']
            logging.debug(f"[generate_date_candidates_in_roi] Fallback: Checking individual word: '{word_text}'")
            is_broad_match_word = parse_date(word_text, is_candidate_phase=True) is not None
            logging.debug(f"[generate_date_candidates_in_roi] Fallback: Broad parse_date for word '{word_text}' (candidate phase): {is_broad_match_word}")
            if is_broad_match_word:
                final_parsed_date = parse_date(word_text, is_candidate_phase=False)
                logging.debug(f"[generate_date_candidates_in_roi] Fallback: Strict parse_date for word '{word_text}': {final_parsed_date}")
                if final_parsed_date:
                    is_dupe = False
                    for cand in candidates:
                        if cand['text'] == word_text and cand['parsed_date'] == final_parsed_date:
                            is_dupe = True
                            break
                    if not is_dupe:
                        candidate_data = {'text': word_text, 'bbox': (word_obj['x0'], word_obj['top'], word_obj['x1'], word_obj['bottom']), 'parsed_date': final_parsed_date, 'y_center': (word_obj['top'] + word_obj['bottom']) / 2, 'x_center': (word_obj['x0'] + word_obj['x1']) / 2}
                        candidates.append(candidate_data)
                        logging.debug(f"[generate_date_candidates_in_roi] Fallback: Added candidate from word: {candidate_data}")
                    else:
                        logging.debug(f"[generate_date_candidates_in_roi] Fallback: Word candidate '{word_text}' is a duplicate. Skipping.")
    logging.debug(f"[generate_date_candidates_in_roi] Found {len(candidates)} date candidates in {column_type_name_for_logging} column ROI {column_roi}: {[c['text'] for c in candidates]}")
    return candidates

def calculate_rarity_scores(all_pages_words_list): # Expects a list of lists of words
    date_counts = defaultdict(int)
    all_text_chunks_for_rarity = []
    for page_words in all_pages_words_list:
        lines = defaultdict(list)
        for word in page_words: lines[round(word['top'] / 5.0) * 5.0].append(word) 
        for _, line_words_on_visual_line in sorted(lines.items()):
            line_words_on_visual_line.sort(key=lambda w: w['x0'])
            line_text = " ".join(w['text'] for w in line_words_on_visual_line)
            all_text_chunks_for_rarity.append(line_text)
            for word_obj in line_words_on_visual_line:
                 all_text_chunks_for_rarity.append(word_obj['text'])
    for text_chunk in list(set(all_text_chunks_for_rarity)):
        parsed_date = parse_date(text_chunk, is_candidate_phase=False)
        if parsed_date: date_counts[parsed_date] += 1
    logging.debug(f"Rarity counts: {dict(date_counts)}")
    return date_counts

def score_date_pair(eff_candidate, exp_candidate,
                    eff_column_header_info, exp_column_header_info,
                    rarity_counts, config):
    logging.debug(f"[score_date_pair] Scoring pair: Eff='{eff_candidate['text']}' ({eff_candidate['parsed_date']}), Exp='{exp_candidate['text']}' ({exp_candidate['parsed_date']})")
    score = 0.0
    notes = [] 
    weights = config.get('ranking_heuristic_weights', {'vertical_alignment': 0.4, 'header_proximity': 0.3, 'plausibility': 0.3})
    logging.debug(f"[score_date_pair] Weights: {weights}")
    eff_date = eff_candidate['parsed_date']
    exp_date = exp_candidate['parsed_date']
    if not (eff_date and exp_date):
        notes.append("One or both dates not parsed.")
        logging.debug(f"[score_date_pair] One or both dates not parsed. Eff: {eff_date}, Exp: {exp_date}. Score: 0.0")
        return 0.0, notes
    if exp_date <= eff_date:
        notes.append(f"Implausible: Exp date {exp_date} not after Eff date {eff_date}.")
        logging.debug(f"[score_date_pair] Implausible: Exp date {exp_date} not after Eff date {eff_date}. Score: 0.0")
        return 0.0, notes
    duration = (exp_date - eff_date).days
    min_duration_days = config.get('date_plausibility', {}).get('min_duration_days', 1)
    max_duration_days = config.get('date_plausibility', {}).get('max_duration_days', 366 * 2) 
    plausibility_score_duration = 1.0
    if not (min_duration_days <= duration <= max_duration_days):
        notes.append(f"Implausible duration: {duration} days. Eff: {eff_date}, Exp: {exp_date}")
        plausibility_score_duration = 0.0 
    logging.debug(f"[score_date_pair] Duration: {duration} days. Min: {min_duration_days}, Max: {max_duration_days}. Duration plausibility score: {plausibility_score_duration}")
    current_plausibility_score_component = weights.get('plausibility', 0.3) * plausibility_score_duration
    score += current_plausibility_score_component
    notes.append(f"Plausibility (duration) contrib: {current_plausibility_score_component:.3f} (raw: {plausibility_score_duration:.2f})")
    logging.debug(f"[score_date_pair] Score after plausibility (duration): {score:.3f}")
    y_diff = abs(eff_candidate['y_center'] - exp_candidate['y_center'])
# Refactored _attempt_localized_date_extraction
def _attempt_localized_date_extraction(
    page_words: List[Dict[str, Any]],
    section_header_info: Dict[str, Any],
    current_region_width: float,
    current_region_height: float, # Corrected: removed extra comma
    section_config_key: str,
    rarity_counts: Dict[date, int],
    config: Dict[str, Any],
    page_num_for_logging: int,
    processing_region_bbox: Tuple[float, float, float, float],
    region_log_prefix: str = ""
) -> Optional[Dict[str, Any]]:
    adaptive_log_prefix = f"[ADAPTIVE_SEARCH {region_log_prefix}]"
    logging.info(f"{adaptive_log_prefix} Attempting localized date extraction for section '{section_config_key}'. Section header: '{section_header_info['text']}' at {section_header_info['bbox']}")
    adaptive_notes = [f"ADAPTIVE_SEARCH ({region_log_prefix}, Section '{section_config_key}'): Triggered."]

    section_header_bbox = section_header_info['bbox'] 

    local_roi_v_padding_above_px = config.get('adaptive_search_local_roi_v_padding_above_px', 15)
    local_roi_v_padding_below_px = config.get('adaptive_search_local_roi_v_padding_below_px', 75)
    
    localized_header_search_roi_top = max(processing_region_bbox[1], section_header_bbox[1] - local_roi_v_padding_above_px)
    localized_header_search_roi_bottom = min(processing_region_bbox[3], section_header_bbox[3] + local_roi_v_padding_below_px)
    
    localized_header_search_roi = (
        processing_region_bbox[0], 
        localized_header_search_roi_top,
        processing_region_bbox[2], 
        localized_header_search_roi_bottom
    )
    if localized_header_search_roi[3] <= localized_header_search_roi[1] or localized_header_search_roi[2] <= localized_header_search_roi[0]:
        logging.debug(f"{adaptive_log_prefix} Localized header search ROI is invalid or has no area: {localized_header_search_roi}. Cannot proceed with adaptive search.")
        adaptive_notes.append(f"Invalid local header search ROI: {localized_header_search_roi}")
        return None # Modified to return None as per original logic for this case
        
    logging.debug(f"{adaptive_log_prefix} Defined localized ROI for finding date HEADERS: {localized_header_search_roi}")
    adaptive_notes.append(f"Local header search ROI: {localized_header_search_roi}")

    local_column_infos = find_column_rois(
        page_words, 
        localized_header_search_roi,
        EFFECTIVE_DATE_KEYWORDS,
        EXPIRATION_DATE_KEYWORDS,
        [], # No policy number column needed for this local search
        current_region_width, # Use current_region_width for context_width in local search
        HEADER_SIMILARITY_THRESHOLD 
    )
    local_eff_col_header_info = local_column_infos.get('effective_column')
    local_exp_col_header_info = local_column_infos.get('expiration_column')

    if not local_eff_col_header_info or not local_exp_col_header_info:
        logging.debug(f"{adaptive_log_prefix} Could not find both Eff and Exp column headers in localized ROI. Eff found: {bool(local_eff_col_header_info)}, Exp found: {bool(local_exp_col_header_info)}")
        adaptive_notes.append(f"Local Eff/Exp headers not found. Eff: {bool(local_eff_col_header_info)}, Exp: {bool(local_exp_col_header_info)}")
        return None

    logging.debug(f"{adaptive_log_prefix} Found local Eff header: '{local_eff_col_header_info['header_text']}' at {local_eff_col_header_info['header_bbox']}, Exp header: '{local_exp_col_header_info['header_text']}' at {local_exp_col_header_info['header_bbox']}")
    adaptive_notes.append(f"Local Eff header: '{local_eff_col_header_info['header_text']}' ({local_eff_col_header_info['score']:.2f}), Exp header: '{local_exp_col_header_info['header_text']}' ({local_exp_col_header_info['score']:.2f})")

    # Define data area based on local headers and original processing_region_bbox
    data_area_top_local = max(local_eff_col_header_info['bbox'][3], local_exp_col_header_info['bbox'][3]) + config.get('section_data_top_offset', 2)
    data_area_top_local = max(data_area_top_local, processing_region_bbox[1]) # Ensure it doesn't go above original region

    data_area_height_config = config.get('section_data_height', 100) # Max height for data search
    data_area_bottom_local = min(data_area_top_local + data_area_height_config, processing_region_bbox[3]) # Don't go below original region

    # Define ROIs for date candidates based on local headers and the calculated data area
    eff_col_bbox_for_section_dates_local = (
        local_eff_col_header_info['bbox'][0] - APP_CONFIG.get('date_column_width_buffer', 10), # x0
        data_area_top_local,                                                                 # top
        local_eff_col_header_info['bbox'][1] + APP_CONFIG.get('date_column_width_buffer', 10) + ((local_eff_col_header_info['bbox'][1] - local_eff_col_header_info['bbox'][0])*1.2), # x1
        data_area_bottom_local                                                               # bottom
    )
    exp_col_bbox_for_section_dates_local = (
        local_exp_col_header_info['bbox'][0] - APP_CONFIG.get('date_column_width_buffer', 10), # x0
        data_area_top_local,                                                                  # top
        local_exp_col_header_info['bbox'][1] + APP_CONFIG.get('date_column_width_buffer', 10) + ((local_exp_col_header_info['bbox'][1] - local_exp_col_header_info['bbox'][0])*1.2),  # x1
        data_area_bottom_local                                                                # bottom
    )
    logging.debug(f"{adaptive_log_prefix} Local Eff Date Candidate ROI: {eff_col_bbox_for_section_dates_local}")
    logging.debug(f"{adaptive_log_prefix} Local Exp Date Candidate ROI: {exp_col_bbox_for_section_dates_local}")
    adaptive_notes.append(f"Local Eff Date ROI: {eff_col_bbox_for_section_dates_local}, Exp Date ROI: {exp_col_bbox_for_section_dates_local}")

    local_eff_candidates = generate_date_candidates_in_roi(page_words, eff_col_bbox_for_section_dates_local, f"LOCAL effective ({section_config_key}, {region_log_prefix})")
    local_exp_candidates = generate_date_candidates_in_roi(page_words, exp_col_bbox_for_section_dates_local, f"LOCAL expiration ({section_config_key}, {region_log_prefix})")
    
    logging.debug(f"{adaptive_log_prefix} Found {len(local_eff_candidates)} local Eff candidates, {len(local_exp_candidates)} local Exp candidates.")
    adaptive_notes.append(f"Local Eff candidates: {len(local_eff_candidates)}, Exp candidates: {len(local_exp_candidates)}")

    if not local_eff_candidates or not local_exp_candidates:
        logging.debug(f"{adaptive_log_prefix} Not enough local candidates found. Eff: {len(local_eff_candidates)}, Exp: {len(local_exp_candidates)}")
        return {'effective_date': None, 'expiration_date': None, 'confidence': 0.0, 'is_valid': False, 'raw_effective_text': None, 'raw_expiration_text': None, 'notes': adaptive_notes}

    best_local_pair = None
    highest_local_score = -1.0

    for eff_c in local_eff_candidates:
        for exp_c in local_exp_candidates:
            score_result = score_date_pair(eff_c, exp_c, local_eff_col_header_info, local_exp_col_header_info, rarity_counts, config)
            if score_result is not None:
                score, score_notes_for_pair = score_result
                if score > highest_local_score:
                    highest_local_score = score
                best_local_pair = (eff_c, exp_c, score_notes_for_pair)
    
    if best_local_pair:
        eff_cand, exp_cand, pair_notes = best_local_pair
        final_confidence = highest_local_score 
        is_valid_local = final_confidence >= config.get('confidence_threshold', 0.80) 
        result = {
            'effective_date': eff_cand['parsed_date'],
            'expiration_date': exp_cand['parsed_date'],
            'confidence': final_confidence,
            'is_valid': is_valid_local,
            'raw_effective_text': eff_cand['text'],
            'raw_expiration_text': exp_cand['text'],
            'notes': adaptive_notes + pair_notes
        }
        logging.info(f"{adaptive_log_prefix} Found best local pair for '{section_config_key}'. Eff: {result['effective_date']}, Exp: {result['expiration_date']}, Conf: {result['confidence']:.3f}, Valid: {result['is_valid']}")
        return result
    else:
        logging.info(f"{adaptive_log_prefix} No suitable date pair found for section '{section_config_key}' using local headers.")
        adaptive_notes.append("No suitable local date pair found.")
        return {'effective_date': None, 'expiration_date': None, 'confidence': 0.0, 'is_valid': False, 'raw_effective_text': None, 'raw_expiration_text': None, 'notes': adaptive_notes}

def deskew_image(image_np: np.ndarray) -> np.ndarray:
    """Deskews an image using projection profile method."""
    logging.debug("[deskew_image] Starting deskew process.")
    grayscale = rgb2gray(image_np) if len(image_np.shape) == 3 else image_np
    logging.debug(f"[deskew_image] Grayscale image shape: {grayscale.shape}")
    
    # Robust binarization for angle detection
    try:
        thresh_value = threshold_otsu(grayscale)
        binary = grayscale > thresh_value
        logging.debug(f"[deskew_image] OTSU threshold value: {thresh_value}")
    except Exception as e: # Catch potential errors if image is all white/black
        logging.warning(f"[deskew_image] OTSU thresholding failed: {e}. Using simple mean threshold.")
        if np.mean(grayscale) < 128 : # Mostly dark
             binary = grayscale > (np.min(grayscale) + np.std(grayscale))
        else: # Mostly light
             binary = grayscale < (np.max(grayscale) - np.std(grayscale))

    logging.debug(f"[deskew_image] Binary image shape: {binary.shape}, dtype: {binary.dtype}, unique values: {np.unique(binary)}")

    angles = np.arange(-5, 5.1, 0.1) # Test a range of angles
    scores = []

    for angle in angles:
        rotated = skimage_rotate(binary, angle, resize=False, cval=0, mode='constant') # cval=0 for black padding
        hist = np.sum(rotated, axis=1)
        
        # More robust peak/valley detection for score calculation
        # We are looking for sharp changes, so variance or std dev of the histogram might be good
        score = np.var(hist) # Variance of the projection profile
        scores.append(score)
        logging.debug(f"[deskew_image] Angle: {angle:.2f}, Score (variance): {score:.2f}")

    if not scores:
        logging.warning("[deskew_image] No scores generated for angles. Returning original image.")
        return image_np

    best_angle_idx = np.argmax(scores)
    best_angle = angles[best_angle_idx]
    logging.info(f"[deskew_image] Best skew angle determined: {best_angle:.2f} degrees with score {scores[best_angle_idx]:.2f}.")

    if abs(best_angle) < 0.05: # If angle is very small, no need to rotate
        logging.info("[deskew_image] Skew angle is negligible. Returning original image.")
        return image_np

    # Rotate the original image (not the binary one used for angle detection)
    rotated_original = skimage_rotate(image_np, best_angle, resize=False, cval=1, order=1, mode='constant') # cval=1 for white padding
    # Convert from float (0-1) back to uint8 (0-255) if necessary
    if rotated_original.dtype == np.float64 or rotated_original.dtype == np.float32:
        rotated_original = (rotated_original * 255).astype(np.uint8)
    logging.debug(f"[deskew_image] Rotated original image shape: {rotated_original.shape}, dtype: {rotated_original.dtype}")
    return rotated_original

def adaptive_binarize_image(image_np_gray: np.ndarray) -> np.ndarray:
    """Applies adaptive thresholding to a grayscale image."""
    logging.debug(f"[adaptive_binarize_image] Starting. Input shape: {image_np_gray.shape}")
    # Ensure block size is odd and greater than 1
    block_size = ADAPTIVE_THRESH_BLOCK_SIZE
    if block_size <= 1: block_size = 11 
    if block_size % 2 == 0: block_size += 1 
    
    try:
        binary_image = cv2.adaptiveThreshold(
            image_np_gray, 
            255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY_INV, # Invert to make text black
            block_size, 
            ADAPTIVE_THRESH_C
        )
        logging.debug(f"[adaptive_binarize_image] Applied adaptive thresholding. Block size: {block_size}, C: {ADAPTIVE_THRESH_C}")
    except cv2.error as e:
        logging.error(f"[adaptive_binarize_image] OpenCV error during adaptiveThreshold: {e}. Returning original grayscale image.")
        return image_np_gray # Or handle differently, e.g., raise error or try global threshold
    
    return binary_image

def detect_columns_heuristic_robust(
    page_words: List[Dict[str, Any]], 
    page_width: float, 
    page_height: float,
    config: Dict[str, Any]
) -> List[Tuple[float, float, float, float]]:
    """
    Detects columns in a list of words from a page using a more robust heuristic approach.
    Focuses on vertical whitespace gaps.
    """
    logging.debug(f"[detect_columns_heuristic_robust] Starting column detection. Page width: {page_width}, Page height: {page_height}")
    if not page_words:
        logging.debug("[detect_columns_heuristic_robust] No words on page, returning single column covering full page.")
        return [(0, 0, page_width, page_height)]

    # Configuration for column detection
    column_config = config.get('column_detection_heuristic', {})
    min_col_width_ratio = column_config.get('min_column_width_ratio', 0.1)  # Min width of a column as ratio of page width
    min_gap_width_ratio = column_config.get('min_gap_width_ratio', 0.03)    # Min width of a gap as ratio of page width
    projection_resolution = column_config.get('projection_resolution', 1000) # Number of bins for x-projection
    peak_prominence_factor = column_config.get('peak_prominence_factor', 0.1) # How much a peak must stand out
    
    min_col_width_px = page_width * min_col_width_ratio
    min_gap_width_px = page_width * min_gap_width_ratio
    logging.debug(f"[detect_columns_heuristic_robust] Min col width (px): {min_col_width_px:.1f}, Min gap width (px): {min_gap_width_px:.1f}")

    # Create a horizontal projection profile (sum of black pixels along x-axis)
    # To do this without rendering, we can use the bounding boxes of words
    x_projection = np.zeros(projection_resolution)
    for word in page_words:
        start_bin = int(word['x0'] / page_width * projection_resolution)
        end_bin = int(word['x1'] / page_width * projection_resolution)
        x_projection[start_bin:end_bin] += (word['bottom'] - word['top']) # Weight by word height

    # Smooth the projection to reduce noise
    smoothing_window = max(5, int(projection_resolution * 0.01)) # Window size for smoothing
    if smoothing_window % 2 == 0: smoothing_window +=1 # Must be odd
    
    # Using a simple moving average for smoothing, can be replaced with Gaussian if needed
    if len(x_projection) > smoothing_window:
         x_projection_smooth = np.convolve(x_projection, np.ones(smoothing_window)/smoothing_window, mode='same')
    else:
         x_projection_smooth = x_projection # Not enough data to smooth meaningfully
    logging.debug(f"[detect_columns_heuristic_robust] Smoothed x-projection profile (first 20 values): {x_projection_smooth[:20]}")

    # Find valleys (potential column gaps) in the smoothed inverted profile
    # We look for peaks in the *negative* of the profile, or valleys in the original
    inverted_profile = np.max(x_projection_smooth) - x_projection_smooth
    
    # Prominence: A peak must be more prominent than a fraction of the profile's range
    required_prominence = (np.max(inverted_profile) - np.min(inverted_profile)) * peak_prominence_factor
    
    # Distance: Minimum distance between valleys (related to min_col_width_px)
    required_distance = int(min_col_width_px / page_width * projection_resolution)
    
    valleys, properties = find_peaks(inverted_profile, 
                                     prominence=max(1, required_prominence), # Prominence must be at least 1
                                     distance=max(1, required_distance)) 
    logging.debug(f"[detect_columns_heuristic_robust] Found {len(valleys)} potential valleys at bins: {valleys} with prominences: {properties.get('prominences')}")

    # Convert valley bin indices to page x-coordinates
    gap_centers_x = [(v / projection_resolution * page_width) for v in valleys]
    
    # Filter gaps that are too narrow (based on peak widths from find_peaks)
    # 'widths' property from find_peaks gives the width of the peak in bins
    valid_gaps_x = []
    if 'widths' in properties and len(properties['widths']) == len(gap_centers_x):
        for i, gap_x in enumerate(gap_centers_x):
            gap_width_px = properties['widths'][i] / projection_resolution * page_width
            if gap_width_px >= min_gap_width_px:
                valid_gaps_x.append(gap_x)
                logging.debug(f"[detect_columns_heuristic_robust] Valley at x={gap_x:.1f} has width {gap_width_px:.1f}px. Accepted.")
            else:
                logging.debug(f"[detect_columns_heuristic_robust] Valley at x={gap_x:.1f} has width {gap_width_px:.1f}px (min_gap_px: {min_gap_width_px:.1f}). Rejected.")
    else: # Fallback if widths are not available or mismatch
        valid_gaps_x = gap_centers_x # Use all found gaps if width info is problematic
        if gap_centers_x: logging.warning("[detect_columns_heuristic_robust] Peak width information not used for gap filtering due to properties mismatch or absence.")


    # Define column boundaries based on filtered gaps
    column_boundaries = [0.0] + sorted(list(set(valid_gaps_x))) + [page_width]
    columns = []
    for i in range(len(column_boundaries) - 1):
        x0, x1 = column_boundaries[i], column_boundaries[i+1]
        # Ensure column is not too narrow
        if (x1 - x0) >= min_col_width_px:
            columns.append((x0, 0, x1, page_height)) # (x0, y0, x1, y1)
            logging.debug(f"[detect_columns_heuristic_robust] Defined column: x0={x0:.1f}, x1={x1:.1f}, width={(x1-x0):.1f}px")
        else:
            logging.debug(f"[detect_columns_heuristic_robust] Potential column x0={x0:.1f}, x1={x1:.1f} (width={(x1-x0):.1f}px) is too narrow. Merging or discarding.")
            # Attempt to merge with previous if this makes it valid, otherwise it's absorbed
            if columns and (x1 - columns[-1][0]) >= min_col_width_px :
                 # Extend the last column
                 last_col = columns.pop()
                 columns.append((last_col[0], 0, x1, page_height))
                 logging.debug(f"[detect_columns_heuristic_robust] Merged with previous. New last column: x0={columns[-1][0]:.1f}, x1={columns[-1][2]:.1f}")


    if not columns: # If no columns found (e.g. single column document)
        logging.debug("[detect_columns_heuristic_robust] No distinct columns found based on gaps, assuming single column layout.")
        return [(0, 0, page_width, page_height)]

    # Post-process to merge very narrow columns or ensure full page coverage if needed
    # This part can be enhanced, for now, we trust the gap-based division if columns were found.
    logging.info(f"[detect_columns_heuristic_robust] Detected {len(columns)} columns: {columns}")
    return columns


def get_bbox_area(bbox: Tuple[float, float, float, float]) -> float:
    """Calculates the area of a bounding box."""
    return (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])

def get_bbox_intersection(bbox1: Tuple[float, float, float, float], bbox2: Tuple[float, float, float, float]) -> Optional[Tuple[float, float, float, float]]:
    """Calculates the intersection of two bounding boxes."""
    x_left = max(bbox1[0], bbox2[0])
    y_top = max(bbox1[1], bbox2[1])
    x_right = min(bbox1[2], bbox2[2])
    y_bottom = min(bbox1[3], bbox2[3])

    if x_right < x_left or y_bottom < y_top:
        return None  # No overlap
    return (x_left, y_top, x_right, y_bottom)

def get_iou(bbox1: Tuple[float, float, float, float], bbox2: Tuple[float, float, float, float]) -> float:
    """Calculates the Intersection over Union (IoU) of two bounding boxes."""
    intersection_bbox = get_bbox_intersection(bbox1, bbox2)
    if intersection_bbox is None:
        return 0.0

    intersection_area = get_bbox_area(intersection_bbox)
    area1 = get_bbox_area(bbox1)
    area2 = get_bbox_area(bbox2)
    union_area = area1 + area2 - intersection_area
    return intersection_area / union_area if union_area > 0 else 0.0

def subtract_bbox(main_bbox: Tuple[float, float, float, float], subtract_bbox: Tuple[float, float, float, float]) -> List[Tuple[float, float, float, float]]:
    """
    Subtracts subtract_bbox from main_bbox, returning a list of up to 4
    rectangular regions that represent the remainder of main_bbox.
    This is a simplified version and might not handle all complex overlaps perfectly.
    """
    ix0, iy0, ix1, iy1 = main_bbox
    sx0, sy0, sx1, sy1 = subtract_bbox
    remaining_bboxes = []

    # Check for no overlap or if subtract_bbox completely contains main_bbox
    if sx1 <= ix0 or sx0 >= ix1 or sy1 <= iy0 or sy0 >= iy1: # No overlap
        return [main_bbox]
    if sx0 <= ix0 and sx1 >= ix1 and sy0 <= iy0 and sy1 >= iy1: # subtract_bbox contains main_bbox
        return []

    # Top part
    if iy0 < sy0:
        remaining_bboxes.append((ix0, iy0, ix1, min(iy1, sy0)))
    # Bottom part
    if iy1 > sy1:
        remaining_bboxes.append((ix0, max(iy0, sy1), ix1, iy1))
    # Left part (within the vertical bounds of the subtracted box)
    if ix0 < sx0:
        remaining_bboxes.append((ix0, max(iy0, sy0), min(ix1, sx0), min(iy1, sy1)))
    # Right part (within the vertical bounds of the subtracted box)
    if ix1 > sx1:
        remaining_bboxes.append((max(ix0, sx1), max(iy0, sy0), ix1, min(iy1, sy1)))
        
    # Filter out zero-area bboxes that might result from edge cases
    return [b for b in remaining_bboxes if get_bbox_area(b) > 1e-3]


def reconcile_layout_regions(
    detected_columns: List[Tuple[float, float, float, float]],
    detected_tables: List[Dict[str, Any]], # Expects tables with 'bbox' key
    page_width: float,
    page_height: float,
    config: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Reconciles detected columns and tables into a list of prioritized processing regions.
    Tables take precedence. Columns are then defined by the remaining space.
    """
    logging.debug(f"[reconcile_layout_regions] Starting. Columns: {len(detected_columns)}, Tables: {len(detected_tables)}")
    
    # Configuration
    reconcile_config = config.get('layout_reconciliation', {})
    min_region_area_ratio = reconcile_config.get('min_region_area_ratio_of_page', 0.005) # Minimum area for a region to be considered
    min_region_area_px = page_width * page_height * min_region_area_ratio
    
    # Start with table regions, giving them higher priority
    # Table bboxes are typically [x0, y0, x1, y1] relative to page
    processing_regions = []
    for i, table in enumerate(detected_tables):
        table_bbox = table['bbox_norm'] # Assuming bbox_norm is [x0,y0,x1,y1] in page coords
        processing_regions.append({
            'type': 'table',
            'bbox': table_bbox,
            'priority': 1, # Higher priority for tables
            'source_id': f"table_{i}"
        })
        logging.debug(f"[reconcile_layout_regions] Added table region: {table_bbox}")

    # Now, consider column regions and subtract table areas from them
    remaining_column_parts = []
    if not detected_columns: # If no columns were detected, treat page as one big column
        logging.debug("[reconcile_layout_regions] No columns initially detected, using full page as a base column.")
        initial_column_bboxes = [(0,0, page_width, page_height)]
    else:
        initial_column_bboxes = detected_columns

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
            logging.debug(f"[reconcile_layout_regions] Added column fragment: {col_part_bbox} (from original col {orig_col_idx})")
        else:
            logging.debug(f"[reconcile_layout_regions] Discarded small column fragment: {col_part_bbox} (Area: {get_bbox_area(col_part_bbox):.1f}px, MinArea: {min_region_area_px:.1f}px)")


    # Sort by priority (tables first), then typically top-to-bottom, left-to-right
    processing_regions.sort(key=lambda r: (r['priority'], r['bbox'][1], r['bbox'][0]))
    
    # Optional: Merge overlapping or very close regions of the same type/priority if needed
    # For now, we keep them separate.

    logging.info(f"[reconcile_layout_regions] Reconciled into {len(processing_regions)} processing regions.")
    if processing_regions:
        for r_idx, r_info in enumerate(processing_regions):
             logging.debug(f"  Region {r_idx+1}: Type='{r_info['type']}', BBox={r_info['bbox']}, Prio={r_info['priority']}, ID='{r_info['source_id']}'")
    
    return processing_regions


def transform_tesseract_data_to_pdfplumber_words(tesseract_data: dict, page_height: float) -> list[dict]:
    """
    Transforms Tesseract's OCR data (from pytesseract.image_to_data)
    into a list of word objects similar to pdfplumber's word format.
    Assumes Tesseract data is for a single page.
    """
    words = []
    if not isinstance(tesseract_data, dict) or not all(k in tesseract_data for k in ['level', 'page_num', 'block_num', 'par_num', 'line_num', 'word_num', 'left', 'top', 'width', 'height', 'conf', 'text']):
        logging.error("[transform_tesseract_data] Invalid Tesseract data format.")
        return []

    try:
        num_raw_entries = len(tesseract_data['text'])
        logging.info(f"[transform_tesseract_data] Processing {num_raw_entries} raw entries from Tesseract data.")
    except TypeError: # If tesseract_data['text'] is not subscriptable (e.g. None)
        logging.error("[transform_tesseract_data] 'text' key in Tesseract data is not a list or is missing.")
        return []


    for i in range(num_raw_entries):
        try:
            # We are interested in word-level entries (level 5)
            if int(tesseract_data['level'][i]) == 5:
                text = str(tesseract_data['text'][i]).strip()
                conf = float(tesseract_data['conf'][i])
                
                # Skip empty strings or very low confidence words if needed (e.g. conf < 10)
                if not text or conf < 0: # Tesseract uses -1 for "bad" words / blocks.
                    logging.debug(f"[transform_loop] Index {i}: Skipping word '{text}' due to empty text or low confidence ({conf}).")
                    continue

                # Tesseract's 'top' is from the top of the image.
                # pdfplumber's 'top' is distance from top of page, 'bottom' is distance from top of page.
                # 'x0', 'x1' are distances from left of page.
                x0 = float(tesseract_data['left'][i])
                top = float(tesseract_data['top'][i]) # This is y0 in pdfplumber terms
                width = float(tesseract_data['width'][i])
                height = float(tesseract_data['height'][i])
                
                x1 = x0 + width
                bottom = top + height # This is y1 in pdfplumber terms

                word_obj = {
                    'text': text,
                    'x0': x0,
                    'top': top,    # pdfplumber's y0
                    'x1': x1,
                    'bottom': bottom, # pdfplumber's y1
                    'upright': True, # Assuming standard orientation from Tesseract
                    'direction': 1,  # Assuming LTR
                    'confidence': conf # Store Tesseract confidence
                }
                words.append(word_obj)
                # logging.debug(f"[transform_loop] Index {i}: Added word: {word_obj}")
            # else:
                # logging.debug(f"[transform_loop] Index {i}: Entry is not word-level (level {tesseract_data['level'][i]}). Text: '{tesseract_data['text'][i]}'")
        except (ValueError, TypeError, IndexError) as e:
            logging.error(f"[transform_loop] Error processing Tesseract data at index {i}: {e}. Data: level='{tesseract_data.get('level',[None]* (i+1))[i]}', text='{tesseract_data.get('text',[None]* (i+1))[i]}'")
            continue # Skip this problematic entry

    logging.info(f"[transform_tesseract_data] Transformed {len(words)} words from Tesseract data.")
    return words


def extract_dates_from_pdf(pdf_path, indicator=None):
    print("extract_dates_from_pdf called")
    logging.info(f"[extract_dates_from_pdf] Starting extraction for PDF: {pdf_path}, Indicator: {indicator}")
    extracted_data = {
        "coi_date": None, "insured_name": None, "insured_address": None,
        "gl_policy_number": None, "gl_eff_date": None, "gl_exp_date": None,
        "wc_policy_number": None, "wc_eff_date": None, "wc_exp_date": None,
        "auto_policy_number": None, "auto_eff_date": None, "auto_exp_date": None,
        "umbrella_policy_number": None, "umbrella_eff_date": None, "umbrella_exp_date": None,
        "other_policy_details": [],
        "filename": os.path.basename(pdf_path),
        "notes": [],
        "page_count": 0,
        "processed_layout_regions_count": 0,
        "ml_table_detections_count": 0,
        "heuristic_column_detections_count": 0,
        "final_processing_regions_count": 0
    }
    all_pages_words_for_rarity = [] # For global rarity calculation
    
    try:
        logging.debug(f"[extract_dates_from_pdf] Opening PDF: {pdf_path}")
        with pdfplumber.open(pdf_path) as pdf:
            extracted_data["page_count"] = len(pdf.pages)
            logging.info(f"[extract_dates_from_pdf] PDF '{pdf_path}' has {extracted_data['page_count']} pages.")

            # --- Pass 1: Collect all words from all pages for rarity scoring ---
            for page_idx_loop, page_obj in enumerate(pdf.pages):
                page_num_for_logging = page_idx_loop + 1
                logging.debug(f"[extract_dates_from_pdf] Pre-Pass (Rarity): Processing Page {page_num_for_logging}/{extracted_data['page_count']}")
                page_words_initial = get_words_with_bbox(page_obj)
                
                # --- OCR Fallback for word collection if few words found by pdfplumber ---
                ocr_fallback_word_threshold = APP_CONFIG.get('ocr_fallback_word_threshold_for_rarity', 20)
                if len(page_words_initial) < ocr_fallback_word_threshold:
                    logging.info(f"[extract_dates_from_pdf] Page {page_num_for_logging} (Rarity Pass): Low word count ({len(page_words_initial)}). Attempting OCR fallback.")
                    try:
                        pil_image = page_obj.to_image(resolution=APP_CONFIG.get('ocr_resolution', 300)).original
                        image_np = np.array(pil_image)
                        
                        # Preprocessing for OCR
                        image_np_gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY) if len(image_np.shape) == 3 else image_np
                        if ENABLE_DESKEW: image_np_gray = deskew_image(image_np_gray) # Deskew grayscale
                        if ENABLE_ADAPTIVE_BINARIZATION: image_np_processed_for_ocr = adaptive_binarize_image(image_np_gray)
                        else: image_np_processed_for_ocr = image_np_gray # Use grayscale if not binarizing

                        ocr_lang = APP_CONFIG.get('ocr_language', 'eng')
                        custom_ocr_config = APP_CONFIG.get('tesseract_custom_config', r'--oem 3 --psm 6')
                        tesseract_data = pytesseract.image_to_data(image_np_processed_for_ocr, lang=ocr_lang, config=custom_ocr_config, output_type=pytesseract.Output.DICT)
                        
                        ocr_words = transform_tesseract_data_to_pdfplumber_words(tesseract_data, page_obj.height)
                        logging.info(f"[extract_dates_from_pdf] Page {page_num_for_logging} (Rarity Pass): OCR fallback yielded {len(ocr_words)} words.")
                        if len(ocr_words) > len(page_words_initial): # Use OCR words if more were found
                            page_words_initial = ocr_words
                            extracted_data["notes"].append(f"Page {page_num_for_logging} (Rarity Pass): Used OCR fallback for word collection ({len(ocr_words)} words).")
                    except Exception as ocr_err:
                        logging.error(f"[extract_dates_from_pdf] Page {page_num_for_logging} (Rarity Pass): OCR fallback failed: {ocr_err}", exc_info=True)
                        extracted_data["notes"].append(f"Page {page_num_for_logging} (Rarity Pass): OCR fallback failed: {ocr_err}")
                
                all_pages_words_for_rarity.append(page_words_initial)
            
            # Calculate rarity scores based on all words from all pages
            rarity_counts = calculate_rarity_scores(all_pages_words_for_rarity)
            extracted_data["notes"].append(f"Calculated global date rarity from {len(all_pages_words_for_rarity)} pages. Unique date forms found: {len(rarity_counts)}")

            # --- Pass 2: Detailed extraction per page ---
            for page_idx_loop, page_obj in enumerate(pdf.pages):
                page_idx = page_idx_loop # Keep 0-indexed for list access if needed
                page_num_for_logging_local = page_idx + 1 # 1-indexed for logging
                logging.info(f"[extract_dates_from_pdf] Main Pass: Processing Page {page_num_for_logging_local}/{extracted_data['page_count']}")
                
                page_words = all_pages_words_for_rarity[page_idx] # Use words already collected
                if not page_words:
                    logging.warning(f"[extract_dates_from_pdf] Page {page_num_for_logging_local}: No words found (neither native nor OCR). Skipping detailed processing for this page.")
                    extracted_data["notes"].append(f"Page {page_num_for_logging_local}: No words found to process.")
                    continue

                # --- Layout Analysis: ML Table Detection and Heuristic Column Detection ---
                detected_tables_for_page = []
                pil_image_for_ml = None
                try:
                    pil_image_for_ml = page_obj.to_image(resolution=APP_CONFIG.get('ml_input_resolution', 200)).original
                    detected_tables_for_page = detect_tables_on_page_image(pil_image_for_ml)
                    extracted_data["ml_table_detections_count"] += len(detected_tables_for_page)
                    logging.info(f"[extract_dates_from_pdf] Page {page_num_for_logging_local}: ML detected {len(detected_tables_for_page)} table(s).")
                    if detected_tables_for_page: extracted_data["notes"].append(f"P{page_num_for_logging_local}: ML tables: {len(detected_tables_for_page)}")
                except Exception as ml_err:
                    logging.error(f"[extract_dates_from_pdf] Page {page_num_for_logging_local}: ML table detection failed: {ml_err}", exc_info=True)
                    extracted_data["notes"].append(f"P{page_num_for_logging_local}: ML table detection error: {str(ml_err)[:100]}")

                detected_columns_for_page = []
                try:
                    detected_columns_for_page = detect_columns_heuristic_robust(page_words, page_obj.width, page_obj.height, APP_CONFIG)
                    extracted_data["heuristic_column_detections_count"] += len(detected_columns_for_page)
                    logging.info(f"[extract_dates_from_pdf] Page {page_num_for_logging_local}: Heuristic detected {len(detected_columns_for_page)} column(s).")
                    if detected_columns_for_page and len(detected_columns_for_page) > 1 : extracted_data["notes"].append(f"P{page_num_for_logging_local}: Heuristic columns: {len(detected_columns_for_page)}")
                except Exception as col_err:
                    logging.error(f"[extract_dates_from_pdf] Page {page_num_for_logging_local}: Heuristic column detection failed: {col_err}", exc_info=True)
                    extracted_data["notes"].append(f"P{page_num_for_logging_local}: Column detection error: {str(col_err)[:100]}")
                
                # Reconcile layout regions
                page_processing_regions = reconcile_layout_regions(detected_columns_for_page, detected_tables_for_page, page_obj.width, page_obj.height, APP_CONFIG)
                extracted_data["final_processing_regions_count"] += len(page_processing_regions)
                if not page_processing_regions: # Fallback to full page if no regions defined
                    page_processing_regions = [{'type': 'full_page_fallback', 'bbox': (0,0,page_obj.width, page_obj.height), 'priority': 99, 'source_id': 'full_page_fallback'}]
                    logging.warning(f"[extract_dates_from_pdf] Page {page_num_for_logging_local}: No specific regions after reconciliation. Using full page as fallback.")
                    extracted_data["notes"].append(f"P{page_num_for_logging_local}: Used full page fallback for region processing.")
                
                extracted_data["processed_layout_regions_count"] += len(page_processing_regions)

                # --- Process each region ---
                for region_idx, current_processing_region_info in enumerate(page_processing_regions):
                    current_processing_region_bbox = current_processing_region_info['bbox']
                    region_type = current_processing_region_info['type']
                    region_log_prefix_page = f"P{page_num_for_logging_local}R{region_idx+1}({region_type})"
                    
                    logging.info(f"[extract_dates_from_pdf] {region_log_prefix_page}: Processing region {current_processing_region_bbox}")

                    # Filter words within the current processing region
                    words_in_current_region = [
                        w for w in page_words
                        if get_iou(w, (current_processing_region_bbox[0], current_processing_region_bbox[1], current_processing_region_bbox[2], current_processing_region_bbox[3])) > 0.1 # Ensure some overlap
                    ]
                    if not words_in_current_region:
                        logging.debug(f"[extract_dates_from_pdf] {region_log_prefix_page}: No words found in region. Skipping.")
                        continue
                    
                    logging.debug(f"[extract_dates_from_pdf] {region_log_prefix_page}: Found {len(words_in_current_region)} words in region.")

                    # --- COI Date (typically page-level, but check in first few regions) ---
                    if extracted_data["coi_date"] is None and (page_idx == 0 and region_idx < 2): # Check on first page, first few regions
                        coi_date_roi_height = page_obj.height * APP_CONFIG.get('coi_date_roi_height_ratio', 0.15)
                        coi_date_search_bbox = (0, 0, page_obj.width, coi_date_roi_height) # Top portion of the page
                        
                        # Refine search_bbox to be intersection of current_processing_region_bbox and coi_date_search_bbox
                        # This ensures we only search within the current region if it's in the top part of the page
                        effective_coi_date_search_bbox = get_bbox_intersection(current_processing_region_bbox, coi_date_search_bbox)

                        if effective_coi_date_search_bbox:
                            logging.debug(f"[extract_dates_from_pdf] {region_log_prefix_page}: Searching for COI Date in refined ROI {effective_coi_date_search_bbox}")
                            coi_date_label_roi = find_section_header_roi(words_in_current_region, COI_DATE_LABEL_KEYWORDS)
                            if coi_date_label_roi:
                                label_bbox = coi_date_label_roi['bbox']
                                # Search for date to the right of the label, within a reasonable vertical window
                                date_search_x0 = label_bbox[2] + APP_CONFIG.get('coi_date_offset_x_from_label', 2)
                                date_search_y0 = label_bbox[1] - APP_CONFIG.get('coi_date_vertical_tolerance', 10)
                                date_search_x1 = label_bbox[2] + APP_CONFIG.get('coi_date_search_width_from_label', 150)
                                date_search_y1 = label_bbox[3] + APP_CONFIG.get('coi_date_vertical_tolerance', 10)
                                
                                # Clip to effective_coi_date_search_bbox and page boundaries
                                date_search_x0 = max(date_search_x0, effective_coi_date_search_bbox[0])
                                date_search_y0 = max(date_search_y0, effective_coi_date_search_bbox[1])
                                date_search_x1 = min(date_search_x1, effective_coi_date_search_bbox[2], page_obj.width)
                                date_search_y1 = min(date_search_y1, effective_coi_date_search_bbox[3], page_obj.height)

                                date_value_roi = (date_search_x0, date_search_y0, date_search_x1, date_search_y1)
                                logging.debug(f"[extract_dates_from_pdf] {region_log_prefix_page}: COI Date Label '{coi_date_label_roi['text']}' found. Date value search ROI: {date_value_roi}")
                                
                                if date_value_roi[0] < date_value_roi[2] and date_value_roi[1] < date_value_roi[3]: # Valid ROI
                                    date_candidates_for_coi = generate_date_candidates_in_roi(words_in_current_region, date_value_roi, "COI Date")
                                    if date_candidates_for_coi:
                                        # Sort by x0, then by y0 (preferring top-left most date near label)
                                        date_candidates_for_coi.sort(key=lambda c: (c['bbox'][0], c['bbox'][1]))
                                        extracted_data["coi_date"] = date_candidates_for_coi[0]['parsed_date']
                                        extracted_data["notes"].append(f"P{page_num_for_logging_local}R{region_idx+1}: COI Date found: {extracted_data['coi_date']} (Raw: '{date_candidates_for_coi[0]['text']}')")
                                        logging.info(f"[extract_dates_from_pdf] {region_log_prefix_page}: COI Date extracted: {extracted_data['coi_date']} from '{date_candidates_for_coi[0]['text']}'")
                                else:
                                     logging.debug(f"[extract_dates_from_pdf] {region_log_prefix_page}: COI Date value ROI was invalid: {date_value_roi}")
                            else:
                                logging.debug(f"[extract_dates_from_pdf] {region_log_prefix_page}: COI Date label not found in ROI {effective_coi_date_search_bbox}.")
                        else:
                            logging.debug(f"[extract_dates_from_pdf] {region_log_prefix_page}: Current region {current_processing_region_bbox} does not overlap with COI date search area {coi_date_search_bbox}.")


                    # --- Insured Name and Address (typically page-level, check in first few regions) ---
                    if extracted_data["insured_name"] is None and (page_idx == 0 and region_idx < 3): # Check on first page, first few regions
                        insured_roi_height = page_obj.height * APP_CONFIG.get('insured_section_roi_height_ratio', 0.3)
                        insured_search_bbox_initial = (0, 0, page_obj.width * 0.6, insured_roi_height) # Top-left portion
                        
                        effective_insured_search_bbox = get_bbox_intersection(current_processing_region_bbox, insured_search_bbox_initial)

                        if effective_insured_search_bbox:
                            logging.debug(f"[extract_dates_from_pdf] {region_log_prefix_page}: Searching for Insured Info in ROI {effective_insured_search_bbox}")
                            insured_header_roi = find_section_header_roi(words_in_current_region, INSURED_SECTION_HEADER_KEYWORDS)
                            if insured_header_roi:
                                header_bbox = insured_header_roi['bbox']
                                # Define area below header for name/address
                                info_search_y0 = header_bbox[3] + APP_CONFIG.get('insured_info_offset_y_from_header', 2)
                                info_search_x0 = max(effective_insured_search_bbox[0], header_bbox[0] - 20) # Allow slightly left of header
                                info_search_x1 = min(effective_insured_search_bbox[2], header_bbox[2] + 200) # Extend right
                                info_search_y1 = min(effective_insured_search_bbox[3], info_search_y0 + APP_CONFIG.get('insured_info_search_height', 100))
                                
                                insured_info_roi = (info_search_x0, info_search_y0, info_search_x1, info_search_y1)
                                logging.debug(f"[extract_dates_from_pdf] {region_log_prefix_page}: Insured Header '{insured_header_roi['text']}' found. Info search ROI: {insured_info_roi}")

                                if insured_info_roi[0] < insured_info_roi[2] and insured_info_roi[1] < insured_info_roi[3]:
                                    words_in_insured_info_roi = [w for w in words_in_current_region if get_iou(w, (insured_info_roi[0], insured_info_roi[1], insured_info_roi[2], insured_info_roi[3])) > 0.1]
                                    words_in_insured_info_roi.sort(key=lambda w: (w['top'], w['x0']))
                                    
                                    lines = defaultdict(list)
                                    for word in words_in_insured_info_roi: lines[round(word['top'] / 5.0) * 5.0].append(word)
                                    
                                    text_lines = [" ".join(w['text'] for w in line_words) for _, line_words in sorted(lines.items())]
                                    
                                    if text_lines:
                                        extracted_data["insured_name"] = text_lines[0].strip() # Assume first line is name
                                        logging.info(f"[extract_dates_from_pdf] {region_log_prefix_page}: Insured Name extracted: {extracted_data['insured_name']}")
                                        extracted_data["notes"].append(f"P{page_num_for_logging_local}R{region_idx+1}: Insured Name: {extracted_data['insured_name']}")
                                        if len(text_lines) > 1:
                                            extracted_data["insured_address"] = " ".join(text_lines[1:]).strip() # Rest is address
                                            logging.info(f"[extract_dates_from_pdf] {region_log_prefix_page}: Insured Address extracted: {extracted_data['insured_address']}")
                                            extracted_data["notes"].append(f"P{page_num_for_logging_local}R{region_idx+1}: Insured Address: {extracted_data['insured_address'][:50]}...")
                                else:
                                    logging.debug(f"[extract_dates_from_pdf] {region_log_prefix_page}: No text lines found in Insured Info ROI.")
                            else:
                                logging.debug(f"[extract_dates_from_pdf] {region_log_prefix_page}: Insured header not found in ROI {effective_insured_search_bbox}.")
                        else:
                             logging.debug(f"[extract_dates_from_pdf] {region_log_prefix_page}: Current region {current_processing_region_bbox} does not overlap with Insured info search area {insured_search_bbox_initial}.")


                    # --- Policy Sections (GL, WC, Auto, Umbrella) ---
                    policy_types_to_check = [
                        ("gl", GL_KEYWORDS, "General Liability"),
                        ("wc", WC_KEYWORDS, "Workers Compensation"),
                        ("auto", AUTO_KEYWORDS, "Automobile Liability"),
                        ("umbrella", UMBRELLA_KEYWORDS, "Umbrella Liability")
                    ]

                    for policy_key_prefix, keywords, policy_type_name_for_logging in policy_types_to_check:
                        # Check if we already found dates for this policy type from a previous region/page (unless it's a general text region)
                        # This is a simple check; more sophisticated multi-page aggregation might be needed
                        if extracted_data[f"{policy_key_prefix}_eff_date"] and extracted_data[f"{policy_key_prefix}_exp_date"] and region_type != 'full_page_fallback':
                            logging.debug(f"[extract_dates_from_pdf] {region_log_prefix_page}: Dates for {policy_type_name_for_logging} already found. Skipping search in this region.")
                            continue

                        logging.debug(f"[extract_dates_from_pdf] {region_log_prefix_page}: Searching for {policy_type_name_for_logging} section header.")
                        section_header_info = find_section_header_roi(words_in_current_region, keywords)

                        if section_header_info:
                            logging.info(f"[extract_dates_from_pdf] {region_log_prefix_page}: Found {policy_type_name_for_logging} header: '{section_header_info['text']}' at {section_header_info['bbox']}")
                            extracted_data["notes"].append(f"P{page_num_for_logging_local}R{region_idx+1}: Found {policy_type_name_for_logging} header: '{section_header_info['text']}'")
                            
                            # Attempt adaptive/localized date extraction first
                            adaptive_result = _attempt_localized_date_extraction(
                                page_words=page_words, # Pass all page words for context
                                section_header_info=section_header_info,
                                current_region_width=(current_processing_region_bbox[2] - current_processing_region_bbox[0]),
                                current_region_height=(current_processing_region_bbox[3] - current_processing_region_bbox[1]),
                                section_config_key=policy_key_prefix, # e.g. "gl", "wc"
                                rarity_counts=rarity_counts,
                                config=APP_CONFIG,
                                page_num_for_logging=page_num_for_logging_local,
                                processing_region_bbox=current_processing_region_bbox, # The bbox of the current column/table fragment
                                region_log_prefix=region_log_prefix_page
                            )

                            if adaptive_result and adaptive_result.get('is_valid'):
                                logging.info(f"[extract_dates_from_pdf] {region_log_prefix_page}: Adaptive search SUCCESS for {policy_type_name_for_logging}. Eff: {adaptive_result['effective_date']}, Exp: {adaptive_result['expiration_date']}, Conf: {adaptive_result['confidence']:.3f}")
                                extracted_data[f"{policy_key_prefix}_eff_date"] = adaptive_result['effective_date']
                                extracted_data[f"{policy_key_prefix}_exp_date"] = adaptive_result['expiration_date']
                                extracted_data[f"{policy_key_prefix}_policy_number"] = None # Policy num not part of adaptive search yet
                                extracted_data["notes"].extend(adaptive_result.get('notes', []))
                                extracted_data["notes"].append(f"P{page_num_for_logging_local}R{region_idx+1} ({policy_type_name_for_logging}): Adaptive dates found. Eff: {adaptive_result['effective_date']}, Exp: {adaptive_result['expiration_date']}")
                                continue # Move to next policy type if adaptive search was successful

                            elif adaptive_result: # Adaptive search ran but was not valid/confident
                                logging.info(f"[extract_dates_from_pdf] {region_log_prefix_page}: Adaptive search for {policy_type_name_for_logging} did not yield a confident result. Notes: {adaptive_result.get('notes')}")
                                extracted_data["notes"].extend(adaptive_result.get('notes', []))
                                extracted_data["notes"].append(f"P{page_num_for_logging_local}R{region_idx+1} ({policy_type_name_for_logging}): Adaptive search no confident dates.")
                            
                            # Fallback to broader column search if adaptive failed or wasn't confident
                            logging.debug(f"[extract_dates_from_pdf] {region_log_prefix_page}: Adaptive search failed or not confident for {policy_type_name_for_logging}. Falling back to broader column search within region.")
                            
                            # Define search ROI for columns below this header, within the current_processing_region_bbox
                            header_actual_bottom = section_header_info['bbox'][3]
                            col_search_roi_top = header_actual_bottom + APP_CONFIG.get('column_search_offset_y_from_header', 2)
                            col_search_roi_bottom = current_processing_region_bbox[3] # Limit to bottom of current region
                            col_search_roi_left = current_processing_region_bbox[0]
                            col_search_roi_right = current_processing_region_bbox[2]

                            if col_search_roi_top >= col_search_roi_bottom: # No space below header in this region
                                logging.debug(f"[extract_dates_from_pdf] {region_log_prefix_page}: No space below {policy_type_name_for_logging} header in current region for column search. Top: {col_search_roi_top}, Bottom: {col_search_roi_bottom}")
                                continue

                            policy_section_column_search_roi = (col_search_roi_left, col_search_roi_top, col_search_roi_right, col_search_roi_bottom)
                            logging.debug(f"[extract_dates_from_pdf] {region_log_prefix_page}: Defined ROI for {policy_type_name_for_logging} column search: {policy_section_column_search_roi}")

                            column_infos_for_section = find_column_rois(
                                words_in_current_region, # Search only words within this region
                                policy_section_column_search_roi,
                                EFFECTIVE_DATE_KEYWORDS,
                                EXPIRATION_DATE_KEYWORDS,
                                POLICY_NUMBER_COLUMN_KEYWORDS,
                                current_processing_region_bbox[2] - current_processing_region_bbox[0], # Width of current region
                                HEADER_SIMILARITY_THRESHOLD
                            )

                            eff_col_info_section = column_infos_for_section.get('effective_column')
                            exp_col_info_section = column_infos_for_section.get('expiration_column')
                            pol_num_col_info_section = column_infos_for_section.get('policy_number_column')

                            # Extract dates and policy numbers if columns are found
                            if eff_col_info_section and exp_col_info_section:
                                eff_date_candidates_section = generate_date_candidates_in_roi(words_in_current_region, eff_col_info_section['bbox'], f"{policy_type_name_for_logging} Effective")
                                exp_date_candidates_section = generate_date_candidates_in_roi(words_in_current_region, exp_col_info_section['bbox'], f"{policy_type_name_for_logging} Expiration")
                                
                                best_pair_score_section = -1.0
                                best_date_pair_section = None
                                pair_notes_section = []

                                for eff_cand_s in eff_date_candidates_section:
                                    for exp_cand_s in exp_date_candidates_section:
                                        score_result_s = score_date_pair(eff_cand_s, exp_cand_s, eff_col_info_section, exp_col_info_section, rarity_counts, APP_CONFIG)
                                        if score_result_s is not None:
                                            current_score_s, current_notes_s = score_result_s
                                            if current_score_s > best_pair_score_section:
                                                best_pair_score_section = current_score_s
                                            best_date_pair_section = (eff_cand_s, exp_cand_s)
                                            pair_notes_section = current_notes_s
                                
                                if best_date_pair_section and best_pair_score_section >= APP_CONFIG.get('confidence_threshold', 0.7): # Check confidence
                                    extracted_data[f"{policy_key_prefix}_eff_date"] = best_date_pair_section[0]['parsed_date']
                                    extracted_data[f"{policy_key_prefix}_exp_date"] = best_date_pair_section[1]['parsed_date']
                                    extracted_data["notes"].append(f"P{page_num_for_logging_local}R{region_idx+1} ({policy_type_name_for_logging}): Dates found. Eff: {best_date_pair_section[0]['parsed_date']} (Raw: '{best_date_pair_section[0]['text']}'), Exp: {best_date_pair_section[1]['parsed_date']} (Raw: '{best_date_pair_section[1]['text']}'), Score: {best_pair_score_section:.3f}")
                                    extracted_data["notes"].extend(pair_notes_section)
                                    logging.info(f"[extract_dates_from_pdf] {region_log_prefix_page}: {policy_type_name_for_logging} Dates: Eff={best_date_pair_section[0]['parsed_date']}, Exp={best_date_pair_section[1]['parsed_date']}, Score={best_pair_score_section:.3f}")
                                else:
                                    logging.debug(f"[extract_dates_from_pdf] {region_log_prefix_page}: No confident date pair found for {policy_type_name_for_logging} in this region. Best score: {best_pair_score_section:.3f}")
                                    extracted_data["notes"].append(f"P{page_num_for_logging_local}R{region_idx+1} ({policy_type_name_for_logging}): No confident date pair. Best score {best_pair_score_section:.3f}")

                            if pol_num_col_info_section:
                                # Extract policy number - simple approach: take text from first line in column ROI
                                pol_num_words = [w for w in words_in_current_region if get_iou(w, (pol_num_col_info_section['bbox'][0], pol_num_col_info_section['bbox'][1], pol_num_col_info_section['bbox'][2], pol_num_col_info_section['bbox'][3])) > 0.1]
                                pol_num_words.sort(key=lambda w: (w['top'], w['x0']))
                                if pol_num_words:
                                    # Try to reconstruct lines within the policy number column
                                    pol_num_lines = defaultdict(list)
                                    for pn_word in pol_num_words: pol_num_lines[round(pn_word['top'] / 5.0) * 5.0].append(pn_word)
                                    
                                    candidate_policy_numbers = []
                                    for _, pn_line_words in sorted(pol_num_lines.items()):
                                        pn_line_text = " ".join(w['text'] for w in pn_line_words).strip()
                                        # Basic filter for policy-like numbers (alphanumeric, some symbols)
                                        if pn_line_text and len(pn_line_text) > 4 and re.match(r'^[a-zA-Z0-9\s\-/#]+$', pn_line_text):
                                            candidate_policy_numbers.append(pn_line_text)
                                    
                                    if candidate_policy_numbers:
                                        # Heuristic: if multiple lines, prefer the one closest vertically to the eff/exp dates if they exist
                                        # For now, just take the first plausible one.
                                        extracted_data[f"{policy_key_prefix}_policy_number"] = candidate_policy_numbers[0]
                                        extracted_data["notes"].append(f"P{page_num_for_logging_local}R{region_idx+1} ({policy_type_name_for_logging}): Policy # found: {candidate_policy_numbers[0]}")
                                        logging.info(f"[extract_dates_from_pdf] {region_log_prefix_page}: {policy_type_name_for_logging} Policy #: {candidate_policy_numbers[0]}")
                                    else:
                                        logging.debug(f"[extract_dates_from_pdf] {region_log_prefix_page}: No plausible policy number text found in {policy_type_name_for_logging} column.")
                                else:
                                     logging.debug(f"[extract_dates_from_pdf] {region_log_prefix_page}: No words found in {policy_type_name_for_logging} policy number column ROI.")
                            else:
                                logging.debug(f"[extract_dates_from_pdf] {region_log_prefix_page}: {policy_type_name_for_logging} policy number column header not found in this region.")
                        else:
                            logging.debug(f"[extract_dates_from_pdf] {region_log_prefix_page}: {policy_type_name_for_logging} section header not found in this region.")
            
            # Consolidate notes
            final_notes = []
            note_counts = defaultdict(int)
            for note in extracted_data["notes"]:
                note_counts[note] +=1
            for note, count in note_counts.items():
                if count > 1: final_notes.append(f"{note} (x{count})")
                else: final_notes.append(note)
            extracted_data["notes"] = final_notes

    except FileNotFoundError:
        logging.error(f"[extract_dates_from_pdf] PDF file not found: {pdf_path}")
        extracted_data["notes"].append(f"ERROR: PDF file not found at {pdf_path}")
    except PDFSyntaxError as e:
        logging.error(f"[extract_dates_from_pdf] PDFSyntaxError for {pdf_path}: {e}", exc_info=True)
        extracted_data["notes"].append(f"ERROR: PDFSyntaxError for {pdf_path}: {e}")
    except Exception as e:
        logging.error(f"[extract_dates_from_pdf] Unexpected error processing {pdf_path}: {e}", exc_info=True)
        extracted_data["notes"].append(f"ERROR: Unexpected error processing {pdf_path}: {e}")

    logging.info(f"[extract_dates_from_pdf] Finished extraction for PDF: {pdf_path}. GL Eff: {extracted_data['gl_eff_date']}, GL Exp: {extracted_data['gl_exp_date']}")
    return extracted_data, extracted_data["notes"] # Return tuple (data_dict, notes_list)

# Example usage (for testing this module directly)
if __name__ == '__main__':
    # Configure logging for standalone testing
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    
    # --- Test with a specific PDF ---
    # Replace with an actual PDF path for testing
    # test_pdf_path = r"C:\path\to\your\test\coi.pdf" 
    test_pdf_path = r"C:\Users\Butle\Desktop\Preston\gitRepos\coi-auditor\tests\fixtures\Sainz Construction_2024-05-09.pdf"

    if os.path.exists(test_pdf_path):
        logging.info(f"--- Running test extraction for: {test_pdf_path} ---")
        data, notes = extract_dates_from_pdf(test_pdf_path)
        print("\n--- Extracted Data ---")
        for key, value in data.items():
            if key != "notes":
                print(f"{key}: {value}")
        print("\n--- Processing Notes ---")
        for note in notes:
            print(note)
        
        # --- Test find_coi_pdfs ---
        # Create a dummy directory structure and files for testing find_coi_pdfs
        dummy_pdf_dir = "dummy_test_pdfs"
        os.makedirs(dummy_pdf_dir, exist_ok=True)
        dummy_files_info = [
            ("Sub A_2023-01-01.pdf", "Sub A"),
            ("Sub A_GL_2023-02-01.pdf", "Sub A"),
            ("Sub B Company_2023-03-01.pdf", "Sub B Company"),
            ("SubC_NoDate.pdf", "SubC"),
            ("Another Company_WC_2023-04-01.pdf", "Another Company")
        ]
        for fname, _ in dummy_files_info:
            with open(os.path.join(dummy_pdf_dir, fname), "w") as f:
                f.write("dummy pdf content")

        print("\n--- Testing find_coi_pdfs ---")
        test_subs = ["Sub A", "Sub B Company", "SubC", "Another Company", "NonExistent Sub"]
        for sub_name_test in test_subs:
            found = find_coi_pdfs(dummy_pdf_dir, sub_name_test)
            print(f"For '{sub_name_test}': Found {found}")

        # Test with direct path
        direct_path_test_file = os.path.join(dummy_pdf_dir, dummy_files_info[1][0]) # Sub A_GL_2023-02-01.pdf
        found_direct = find_coi_pdfs(dummy_pdf_dir, "Sub A", direct_pdf_path=Path(direct_path_test_file))
        print(f"For 'Sub A' (direct path '{direct_path_test_file}'): Found {found_direct}")
        
        # Cleanup dummy files and directory
        for fname, _ in dummy_files_info:
            try: os.remove(os.path.join(dummy_pdf_dir, fname))
            except OSError: pass
        try: os.rmdir(dummy_pdf_dir)
        except OSError: pass
        
    else:
        print(f"Test PDF not found: {test_pdf_path}")
