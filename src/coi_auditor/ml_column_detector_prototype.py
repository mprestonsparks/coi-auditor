import os
import json # Added for JSON output
from pdf2image import convert_from_path
from PIL import Image as PILImage, ImageDraw # Alias Image to PILImage to avoid conflict if Image class is defined locally
from transformers.models.auto.image_processing_auto import AutoImageProcessor
from transformers.models.table_transformer.modeling_table_transformer import TableTransformerForObjectDetection
import torch
from typing import Optional, List, Dict, Any # Added missing imports
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
# PDF_DIR should point to the relocated test corpus
PDF_DIR = "tests/harness/corpus/pdfs"
# Using one of the PDFs from the corpus
# Ensure FernandoHernandez_2024-09-19.pdf is in tests/harness/corpus/pdfs/
PDF_NAME = "FernandoHernandez_2024-09-19.pdf" # This specific PDF_NAME is not used when iterating all files
# PDF_NAME = "S&G Siding and Gutters_2023-10-18.pdf" # Alternative test PDF
OUTPUT_DIR = "output/ml_prototype_output" # New output directory
os.makedirs(OUTPUT_DIR, exist_ok=True)
# The line below is redundant as OUTPUT_DIR itself is the target.
# os.makedirs(os.path.join(OUTPUT_DIR), exist_ok=True)

# --- Tesseract Configuration (Important for some LayoutLM versions or if explicitly used) ---
# Tesseract path can be configured via environment variable TESSERACT_CMD if needed
# For LayoutLMv3, direct OCR data input is less critical as it processes images.
# However, having Tesseract installed can be beneficial for some processor functionalities.
# We will proceed assuming LayoutLMv3's image processing capabilities are primary for this prototype.
try:
    import pytesseract
    tesseract_cmd = os.getenv('TESSERACT_CMD')
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
except ImportError:
    # pytesseract not installed, which is fine for this prototype
    pass

def convert_pdf_page_to_image(pdf_path: str, page_number: int = 0, poppler_path: Optional[str] = None) -> Optional[PILImage.Image]:
    """Converts a specific page of a PDF to a PIL Image."""
    try:
        if poppler_path:
            images = convert_from_path(
                pdf_path,
                first_page=page_number + 1,
                last_page=page_number + 1,
                dpi=300,
                poppler_path=poppler_path
            )
        else:
            images = convert_from_path(
                pdf_path,
                first_page=page_number + 1,
                last_page=page_number + 1,
                dpi=300
            )
        if images:
            return images[0]
        else:
            print(f"Could not convert page {page_number} of {pdf_path} to image.")
            return None
    except Exception as e:
        print(f"Error converting PDF to image: {e}")
        print("Please ensure Poppler is installed and in your PATH.")
        print("For Windows, download Poppler from: https://github.com/oschwartz10612/poppler-windows/releases")
        print("Then add the 'bin' directory to your system PATH.")
        return None

def detect_layout_objects(image: Optional[PILImage.Image], model, processor, device) -> List[Dict[str, Any]]:
    """
    Detects objects in an image using a pre-trained Table-Transformer model,
    processes the results, and returns a sorted list of detected objects.
    """
    if image is None:
        return [] # Return empty list if image is None

    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()} # Move all input tensors to the device
    outputs = model(**inputs)

    # Convert outputs (bounding boxes and class logits) to COCO API format
    # image.size should be (width, height)
    target_sizes = torch.tensor([image.size[::-1]], device=device) # size is (width, height), tensor wants (height, width)
    results = processor.post_process_object_detection(outputs, target_sizes=target_sizes, threshold=0.5)[0]
    # Changed threshold to 0.5

    raw_boxes = results["boxes"].tolist()
    raw_scores = results["scores"].tolist()
    raw_labels = results["labels"].tolist()

    model_labels_map = model.config.id2label
    
    detected_objects = []
    for i, box in enumerate(raw_boxes):
        label_id = raw_labels[i]
        detected_object = {
            "id": i, # Sequential ID within this image
            "label": model_labels_map[label_id],
            "score": float(raw_scores[i]), # Ensure score is float
            "box": [round(coord, 2) for coord in box] # Round box coordinates
        }
        detected_objects.append(detected_object)

    # Sort detected objects by the x-coordinate of their bounding boxes (left-to-right)
    detected_objects.sort(key=lambda obj: obj['box'][0])
    
    # Update IDs after sorting to maintain sequential order in the final list
    for idx, obj in enumerate(detected_objects):
        obj['id'] = idx

    print(f"Detected {len(detected_objects)} objects.")
    for obj in detected_objects:
        print(f"  ID: {obj['id']}, Label: {obj['label']}, Score: {obj['score']:.2f}, Box: {obj['box']}")

    return detected_objects

def draw_boxes_on_image(image: Optional[PILImage.Image], detected_objects: List[Dict[str, Any]], output_path: str ="output_with_boxes.png"):
    """Draws bounding boxes on an image and saves it."""
    if image is None or not detected_objects:
        return

    draw = ImageDraw.Draw(image)
    for obj in detected_objects:
        # Each box is [xmin, ymin, xmax, ymax]
        draw.rectangle(obj['box'], outline="red", width=2)
    image.save(output_path)
    print(f"Saved image with detected boxes to {output_path}")


def main():
    print("Starting ML Table/Column Detection Prototype (Table-Transformer)...")

    # Standardize Model and Device Handling
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # Load pre-trained Table-Transformer model and processor once
    print("Loading Table-Transformer model (microsoft/table-transformer-detection) and processor...")
    try:
        processor = AutoImageProcessor.from_pretrained("microsoft/table-transformer-detection")
        model = TableTransformerForObjectDetection.from_pretrained("microsoft/table-transformer-detection")
        model.to(device) # Move model to the selected device
        model.eval()     # Set model to evaluation mode
        print("Table-Transformer model and processor loaded successfully and moved to device.")
    except Exception as e:
        print(f"Error loading Table-Transformer model/processor: {e}")
        print("Ensure you have an internet connection to download the model,")
        print("and that the 'transformers', 'torch', and potentially 'timm' libraries are installed correctly.")
        print("If 'timm' is missing, try: pip install timm")
        return
    print("Model and processor loaded.")

    # Get Poppler path from environment variable
    poppler_bin_path = os.getenv('POPPLER_BIN_PATH')
    if not poppler_bin_path:
        print("Warning: POPPLER_BIN_PATH environment variable not set.")
        print("Please set POPPLER_BIN_PATH to the path of your Poppler bin directory,")
        print("or ensure Poppler utilities are available in your system PATH.")
        print("Example: POPPLER_BIN_PATH=C:\\cli\\poppler-24.08.0\\Library\\bin")
        return

    pdf_files = [f for f in os.listdir(PDF_DIR) if f.lower().endswith(".pdf")]
    if not pdf_files:
        print(f"No PDF files found in {PDF_DIR}")
        return

    for pdf_name in pdf_files:
        pdf_file_path = os.path.join(PDF_DIR, pdf_name)
        print(f"\nProcessing PDF: {pdf_file_path}")

        if not os.path.exists(pdf_file_path):
            print(f"PDF file not found: {pdf_file_path}")
            continue # Skip to the next file

        # 1. Convert PDF page to image (first page, page_number=0)
        page_image = convert_pdf_page_to_image(pdf_file_path, page_number=0, poppler_path=poppler_bin_path)
        if page_image is None:
            print(f"Failed to convert PDF page to image for {pdf_name}. Skipping.")
            continue

        # Save the converted image for inspection
        base_name = os.path.splitext(pdf_name)[0]
        converted_image_path = os.path.join(OUTPUT_DIR, f"{base_name}_page_0_converted.png")
        try:
            page_image.save(converted_image_path)
            print(f"Saved converted PDF page to {converted_image_path}")
        except Exception as e:
            print(f"Error saving converted image {converted_image_path}: {e}")


        # 3. Perform inference
        print(f"Performing object detection with Table-Transformer for {pdf_name}...")
        # Pass a copy of the image to avoid modification by drawing functions if any
        # And pass the device
        detected_objects_list = detect_layout_objects(page_image.copy(), model, processor, device)

        if detected_objects_list:
            print(f"Successfully detected {len(detected_objects_list)} objects in {pdf_name} using Table-Transformer.")
            
            # 4. Save Structured Output to JSON
            json_output_filename = f"{base_name}_page_0_tatr_detections.json"
            json_output_path = os.path.join(OUTPUT_DIR, json_output_filename)
            try:
                with open(json_output_path, 'w') as f_json:
                    json.dump(detected_objects_list, f_json, indent=4)
                print(f"Saved structured detections to {json_output_path}")
            except Exception as e:
                print(f"Error saving JSON output to {json_output_path}: {e}")

            # 5. Maintain Visual Output
            output_image_path = os.path.join(OUTPUT_DIR, f"{base_name}_page_0_tatr_detected.png")
            # Pass detected_objects_list which contains the boxes
            draw_boxes_on_image(page_image.copy(), detected_objects_list, output_image_path)

            # Optional: Print summary of what was detected for this PDF
            print(f"\n--- Detections Summary for {pdf_name} ---")
            for obj in detected_objects_list:
                print(f"  ID: {obj['id']}, Label: {obj['label']}, Score: {obj['score']:.2f}, Box: {obj['box']}")
            print("--- End Summary ---")

        else:
            print(f"No objects detected by Table-Transformer in {pdf_name} or an error occurred during detection.")
            # Create an empty JSON if no objects are detected
            json_output_filename = f"{base_name}_page_0_tatr_detections.json"
            json_output_path = os.path.join(OUTPUT_DIR, json_output_filename)
            try:
                with open(json_output_path, 'w') as f_json:
                    json.dump([], f_json, indent=4) # Save an empty list
                print(f"Saved empty detection list to {json_output_path} as no objects were found.")
            except Exception as e:
                print(f"Error saving empty JSON output to {json_output_path}: {e}")


    print("\nTable-Transformer Prototype execution finished for all PDFs.")
    print(f"Check the '{OUTPUT_DIR}' directory for any generated images.")

if __name__ == "__main__":
    main()