import cv2
import numpy as np
from PIL import Image
from surya.layout import LayoutPredictor
from surya.settings import settings # Keep this for device settings
import pytesseract
from fuzzywuzzy import fuzz
import re
from dateutil import parser
from datetime import datetime

def preprocess_image_for_date_ocr(image_path_or_cv2_image):
    """
    Optimized preprocessing pipeline for date regions in COIs.
    
    Args:
        image_path_or_cv2_image: Path to image file or OpenCV image array
        
    Returns:
        Preprocessed binary image optimized for date OCR
    """
    # Load image if path is provided
    if isinstance(image_path_or_cv2_image, str):
        img = cv2.imread(image_path_or_cv2_image)
        if img is None:
            raise FileNotFoundError(f"Image not found at {image_path_or_cv2_image}")
    elif isinstance(image_path_or_cv2_image, np.ndarray):
        img = image_path_or_cv2_image.copy()
    else:
        raise TypeError("Input must be a file path (str) or an OpenCV image (np.ndarray)")

    # Convert to grayscale if not already
    if len(img.shape) == 2:  # Already grayscale
        gray = img
    else:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Resize for optimal OCR if region is small
    h, w = gray.shape
    if h > 0 and h < 40 and w > 0:  # Small date regions
        scale_factor = 2.0  # Moderate upscale
        gray = cv2.resize(gray, (int(w * scale_factor), int(h * scale_factor)), 
                         interpolation=cv2.INTER_LANCZOS4)

    # Noise reduction - bilateral filter preserves edges better than Gaussian blur
    processed_img = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)
    
    # Binarization - adaptive thresholding handles variable lighting well
    binary_img = cv2.adaptiveThreshold(processed_img, 255, 
                                      cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                      cv2.THRESH_BINARY, 11, 2)
    
    return binary_img

def extract_date_with_tesseract(processed_image_roi):
    """
    Extracts date text from a preprocessed image region using optimal tesseract settings.
    
    Args:
        processed_image_roi: Preprocessed binary image of the date region
        
    Returns:
        Extracted text string
    """
    # For Windows, if Tesseract is not in PATH:
    # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    
    # Define whitelist for dates - digits and common separators only
    date_whitelist = "0123456789/-."
    
    # Try multiple PSM modes to find the best result
    psm_modes = [
        # Assume a single uniform block of text
        f'--oem 3 --psm 6 -c tessedit_char_whitelist="{date_whitelist}"',
        
        # Treat the image as a single text line
        f'--oem 3 --psm 7 -c tessedit_char_whitelist="{date_whitelist}"',
        
        # Sparse text. Find as much text as possible in no particular order
        f'--oem 3 --psm 11 -c tessedit_char_whitelist="{date_whitelist}"',
        
        # Raw line. Treat the image as a single text line
        f'--oem 1 --psm 13 -c tessedit_char_whitelist="{date_whitelist}"'
    ]
    
    results = []
    for config in psm_modes:
        try:
            date_text = pytesseract.image_to_string(processed_image_roi, lang='eng', config=config)
            cleaned_text = date_text.strip()
            if cleaned_text:  # Only add non-empty results
                results.append(cleaned_text)
        except Exception as e:
            print(f"Error with config {config}: {e}")
            
    # Return best result (non-empty) or empty string
    # In a more advanced implementation, you could apply heuristics to select the best result
    return results[0] if results else ""

import re
from dateutil import parser
from datetime import datetime

def post_process_ocr_date_string(ocr_text):
    """
    Clean, correct, and validate OCR output to extract properly formatted dates.
    
    Args:
        ocr_text: Raw text from OCR
        
    Returns:
        Standardized date string in YYYY-MM-DD format or None if invalid
    """
    if not ocr_text or not ocr_text.strip():
        return None

    # 1. Basic cleaning
    cleaned_text = ocr_text.strip()
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
    cleaned_text = re.sub(r'[^\w\s/\-.]', '', cleaned_text)  # Remove non-alphanumeric characters except common separators

    # 2. Character correction for common OCR errors
    corrections = {
        'O': '0', 'o': '0', 'L': '1', 'l': '1', 'I': '1', 
        'S': '5', 's': '5', 'B': '8', 'Z': '2', 'z': '2',
        'A': '4', 'G': '6', 'q': '9', 'g': '9',
        'E': '8', 'T': '7'
    }
    
    temp_text = ""
    for char in cleaned_text:
        temp_text += corrections.get(char, char)
    cleaned_text = temp_text

    # 3. Match common date patterns
    date_patterns = [
        # MM/DD/YYYY or MM-DD-YYYY
        r'\b(?P<month>\d{1,2})[-/.](?P<day>\d{1,2})[-/.](?P<year>\d{4})\b',
        
        # MM/DD/YY or MM-DD-YY
        r'\b(?P<month>\d{1,2})[-/.](?P<day>\d{1,2})[-/.](?P<year>\d{2})\b',
        
        # YYYY-MM-DD or YYYY/MM/DD
        r'\b(?P<year>\d{4})[-/.](?P<month>\d{1,2})[-/.](?P<day>\d{1,2})\b',
        
        # Month Day, Year (e.g., January 1, 2025)
        r'\b(?P<month>\w+) (?P<day>\d{1,2}), (?P<year>\d{4})\b'
    ]

    extracted_date_str = cleaned_text  # Default to cleaned text

    for pattern in date_patterns:
        match = re.search(pattern, cleaned_text, re.IGNORECASE)
        if match:
            extracted_date_str = match.group(0)
            break  # Use first match

    # 4. Validate and standardize with dateutil.parser
    try:
        # For US COIs, month usually comes first (MM/DD/YYYY)
        dt_obj = parser.parse(extracted_date_str, dayfirst=False, yearfirst=False)
        
        # Basic validation - ensure year is in a reasonable range
        current_year = datetime.now().year
        if not (1980 <= dt_obj.year <= current_year + 10):
            return None  # Year out of plausible range
            
        # Return standardized date format
        return dt_obj.strftime('%Y-%m-%d')  # ISO format
        
    except (parser.ParserError, ValueError, TypeError, OverflowError):
        return None  # Failed to parse as valid date

def extract_dates_with_easyocr(image_path, date_field_bboxes):
    """
    Extract dates using EasyOCR instead of pytesseract
    """
    import easyocr
    import numpy as np
    import cv2

    # Initialize reader once (can be slow)
    reader = easyocr.Reader(['en'])
    
    # Load image
    full_image = cv2.imread(image_path)
    if full_image is None:
        raise FileNotFoundError(f"Image not found at {image_path}")
        
    extracted_dates = {}
    
    for i, bbox in enumerate(date_field_bboxes):
        # Crop region based on bbox
        x_min, y_min, x_max, y_max = map(int, bbox)
        
        # Basic validation
        h, w = full_image.shape[:2]
        x_min, y_min = max(0, x_min), max(0, y_min)
        x_max, y_max = min(w, x_max), min(h, y_max)
        
        if x_min >= x_max or y_min >= y_max:
            continue
            
        # Define search area around the header
        search_area_x_min = x_min
        search_area_y_min = y_max  # Search below the header
        search_area_x_max = x_max + 500  # Extend search area to the right
        search_area_y_max = y_max + 100  # Extend search area downwards

        # Ensure search area is within image bounds
        search_area_x_min = max(0, search_area_x_min)
        search_area_y_min = max(0, search_area_y_min)
        search_area_x_max = min(w, search_area_x_max)
        search_area_y_max = min(h, search_area_y_max)
        
        # Crop the region
        date_region = full_image[search_area_y_min:search_area_y_max, search_area_x_min:search_area_x_max]
        
        # Preprocess
        preprocessed_region = preprocess_image_for_date_ocr(date_region)
        
        # OCR with EasyOCR
        result = reader.readtext(preprocessed_region)
        
        # Extract text from EasyOCR result
        raw_text = ' '.join([text for _, text, _ in result])

        print(f"Raw Text before post-processing: {raw_text}")
        
        # Post-process
        processed_date = post_process_ocr_date_string(raw_text)
        
        extracted_dates[f"date_{i}"] = {
            "bbox": bbox,
            "raw_text": raw_text,
            "processed_date": processed_date
        }
        
    return extracted_dates

def debug_ocr_pipeline(image_path, bbox, output_dir="debug_output"):
    """
    Debug the OCR pipeline by saving intermediate images
    """
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    # Load original image
    full_image = cv2.imread(image_path)
    
    # Crop region
    x_min, y_min, x_max, y_max = map(int, bbox)
    cropped = full_image[y_min:y_max, x_min:x_max]
    cv2.imwrite(f"{output_dir}/1_cropped.png", cropped)
    
    # Convert to grayscale
    gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
    cv2.imwrite(f"{output_dir}/2_grayscale.png", gray)
    
    # Resize if needed
    h, w = gray.shape
    if h > 0 and h < 40:
        scale_factor = 2.0
        gray = cv2.resize(gray, (int(w * scale_factor), int(h * scale_factor)), 
                         interpolation=cv2.INTER_LANCZOS4)
        cv2.imwrite(f"{output_dir}/3_resized.png", gray)
    
    # Apply bilateral filter
    bilateral = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)
    cv2.imwrite(f"{output_dir}/4_bilateral.png", bilateral)
    
    # Apply adaptive threshold
    binary = cv2.adaptiveThreshold(bilateral, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                  cv2.THRESH_BINARY, 11, 2)
    cv2.imwrite(f"{output_dir}/5_binary.png", binary)
    
    # Try inverting the image (sometimes helps)
    inverted = cv2.bitwise_not(binary)
    cv2.imwrite(f"{output_dir}/6_inverted.png", inverted)
    
    return {
        "cropped": cropped,
        "gray": gray,
        "bilateral": bilateral,
        "binary": binary,
        "inverted": inverted
    }

def test_ocr_options(images_dict):
    """
    Test different OCR configurations on preprocessed images
    """
    results = {}
    
    # Define whitelist for dates
    date_whitelist = "0123456789/-."
    
    # Test different PSM modes
    psm_modes = [6, 7, 11, 13]
    
    for img_name, img in images_dict.items():
        results[img_name] = {}
        
        # Try both OEM modes (1 and 3)
        for oem in [1, 3]:
            results[img_name][f"oem_{oem}"] = {}
            
            # Try different PSM modes
            for psm in psm_modes:
                config = f'--oem {oem} --psm {psm} -c tessedit_char_whitelist="{date_whitelist}"'
                try:
                    text = pytesseract.image_to_string(img, lang='eng', config=config)
                    results[img_name][f"oem_{oem}"][f"psm_{psm}"] = text.strip()
                except Exception as e:
                    results[img_name][f"oem_{oem}"][f"psm_{psm}"] = f"ERROR: {str(e)}"
    
    # Print results in a readable format
    print("\n=== OCR TEST RESULTS ===")
    for img_name in results:
        print(f"\n## Image: {img_name}")
        for oem_name in results[img_name]:
            print(f"\n-- {oem_name} --")
            for psm_name, text in results[img_name][oem_name].items():
                print(f"{psm_name}: '{text}'")
    
    return results

def test_post_processing():
    """
    Test post-processing with known date strings
    """
    test_strings = [
        "12/25/2023",
        "12/25/23",
        "2023-12-25",
        "12-25-2023",
        "12.25.2023",
        "l2/25/2023",  # l instead of 1
        "12/2S/2023",  # S instead of 5
        "O6/15/2023",  # O instead of 0
        "  06/15/2023  ",  # with spaces
        "06 / 15 / 2023",  # with spaces between parts
        "06152023"  # without separators
    ]
    
    print("\n=== POST-PROCESSING TEST ===")
    for s in test_strings:
        processed = post_process_ocr_date_string(s)
        print(f"Original: '{s}' → Processed: {processed}")

# Load the image
image_path = "debug_page_image.png"  # Replace with the actual path to your image
try:
    image = Image.open(image_path)
    image = image.convert("RGB")  # Ensure the image is in RGB format
except FileNotFoundError:
    print(f"Error: Image not found at {image_path}")
    exit()
except Exception as e:
    print(f"Error: Could not open image: {e}")
    exit()

# Print image information
print(f"Image size: {image.size}")
print(f"Image mode: {image.mode}")

# Initialize LayoutPredictor
print("Initializing LayoutPredictor...")
layout_predictor = LayoutPredictor()

# Run layout detection
print("Running layout detection...")
layout_predictions = layout_predictor.batch_layout_detection([image])

# Define potential header labels
header_labels = ['SectionHeader', 'Title']

# Define known headers (replace with actual known headers)
known_headers = ["CERTIFICATE OF LIABILITY INSURANCE", "COVERAGES", "IMPORTANT"]

# Extract dates
date_field_bboxes = []

# Print layout predictions and extract text
print("Layout Predictions:")
for layout_result in layout_predictions:
    for bbox_obj in layout_result.bboxes:
        if bbox_obj.label in header_labels:
            print(f"  Type: {bbox_obj.label}")
            print(f"  Bbox: {bbox_obj.polygon}")

            # Crop the image
            polygon = bbox_obj.polygon
            x1 = min(p[0] for p in polygon)
            y1 = min(p[1] for p in polygon)
            x2 = max(p[0] for p in polygon)
            y2 = max(p[1] for p in polygon)
            date_field_bboxes.append([x1, y1, x2, y2])

extracted_dates = extract_dates_with_easyocr(image_path, date_field_bboxes)

print("Extracted Dates:")
for key, value in extracted_dates.items():
    print(f"  {key}:")
    print(f"    Raw Text: {value['raw_text']}")
    print(f"    Processed Date: {value['processed_date']}")

# Run diagnostics
if date_field_bboxes:
    debug_info = debug_ocr_pipeline(image_path, date_field_bboxes[0])
    test_ocr_options(debug_info)
    test_post_processing()