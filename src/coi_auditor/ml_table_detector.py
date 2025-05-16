import torch
from PIL import Image
from transformers import AutoImageProcessor, TableTransformerForObjectDetection
from typing import List, Dict, Any
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Global model and processor to avoid reloading on every call
# These will be initialized by a dedicated function.
MODEL = None
PROCESSOR = None
DEVICE = None

def initialize_ml_model(model_name: str = "microsoft/table-transformer-detection"):
    """
    Initializes the Table Transformer model, processor, and device.
    This function should be called once before using detect_tables_on_page_image.
    """
    global MODEL, PROCESSOR, DEVICE
    if MODEL is not None and PROCESSOR is not None and DEVICE is not None:
        logger.info("ML model already initialized.")
        return

    DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using device: {DEVICE} for ML table detection.")

    try:
        logger.info(f"Loading Table-Transformer model ({model_name}) and processor...")
        PROCESSOR = AutoImageProcessor.from_pretrained(model_name)
        MODEL = TableTransformerForObjectDetection.from_pretrained(model_name)
        MODEL.to(DEVICE)
        MODEL.eval()
        logger.info("Table-Transformer model and processor loaded successfully and moved to device.")
    except Exception as e:
        logger.error(f"Error loading Table-Transformer model/processor: {e}", exc_info=True)
        logger.error("Ensure you have an internet connection to download the model,")
        logger.error("and that the 'transformers', 'torch', and potentially 'timm' libraries are installed correctly.")
        logger.error("If 'timm' is missing, try: pip install timm")
        # Raise the exception to signal failure to the calling module
        raise

def detect_tables_on_page_image(page_image: Image.Image) -> List[Dict[str, Any]]:
    """
    Detects table objects in a given PIL Image using the pre-initialized Table-Transformer model.

    Args:
        page_image (Image.Image): The PIL Image object of the page.

    Returns:
        List[Dict[str, Any]]: A list of detected table objects, where each object is a dictionary
                              containing 'label', 'score', and 'box' (coordinates).
                              Returns an empty list if no tables are detected or if the model is not initialized.
    """
    global MODEL, PROCESSOR, DEVICE

    if MODEL is None or PROCESSOR is None or DEVICE is None:
        logger.error("ML model not initialized. Call initialize_ml_model() first.")
        # Or, alternatively, attempt to initialize it here if that's preferred.
        # For now, we require explicit initialization.
        try:
            initialize_ml_model()
        except Exception:
            logger.error("Failed to auto-initialize model during detection call.")
            return []


    if page_image is None:
        logger.warning("Received a None image for table detection.")
        return []

    try:
        inputs = PROCESSOR(images=page_image, return_tensors="pt")
        inputs = inputs.to(DEVICE)
        outputs = MODEL(**inputs)

        target_sizes = torch.tensor([page_image.size[::-1]], device=DEVICE)
        results = PROCESSOR.post_process_object_detection(outputs, target_sizes=target_sizes, threshold=0.5)[0]

        raw_boxes = results["boxes"].tolist()
        raw_scores = results["scores"].tolist()
        raw_labels = results["labels"].tolist()

        model_labels_map = MODEL.config.id2label
        
        detected_objects = []
        for i, box_coords in enumerate(raw_boxes):
            label_id = raw_labels[i]
            label_name = model_labels_map[label_id]
            
            # We are primarily interested in 'table' detections from this model
            if label_name == 'table' or label_name == 'table rotated': # Include rotated tables if model supports
                detected_object = {
                    "id": i,
                    "label": label_name,
                    "score": float(raw_scores[i]),
                    "box": [round(coord, 2) for coord in box_coords] # [xmin, ymin, xmax, ymax]
                }
                detected_objects.append(detected_object)
        
        # Sort detected tables by y-coordinate primarily, then x-coordinate (top-to-bottom, left-to-right)
        detected_objects.sort(key=lambda obj: (obj['box'][1], obj['box'][0]))
        
        # Update IDs after sorting
        for idx, obj in enumerate(detected_objects):
            obj['id'] = idx

        logger.info(f"Detected {len(detected_objects)} table(s) on the page image.")
        # for obj in detected_objects: # Verbose logging, can be enabled if needed
        #     logger.debug(f"  ID: {obj['id']}, Label: {obj['label']}, Score: {obj['score']:.2f}, Box: {obj['box']}")

        return detected_objects

    except Exception as e:
        logger.error(f"Error during table detection on page image: {e}", exc_info=True)
        return []

if __name__ == "__main__":
    # This section is for basic testing of this module if run directly.
    # It's not part of the main application flow.
    print("Testing ml_table_detector.py...")
    
    # Attempt to initialize the model
    try:
        initialize_ml_model()
    except Exception as e:
        print(f"Failed to initialize model for testing: {e}")
        exit()

    # Create a dummy image for testing (replace with actual image loading if needed)
    try:
        # Try to load a test image if available, e.g., from the prototype output
        # This requires a sample image to be present at this path for testing.
        # For robust testing, mock this or ensure a test image is part of the test setup.
        test_image_path = "test_harness/prototype_output/FernandoHernandez_2024-09-19_page_0_converted.png"
        if os.path.exists(test_image_path):
            dummy_image = Image.open(test_image_path).convert("RGB")
            print(f"Loaded test image: {test_image_path}")
        else:
            print(f"Test image not found at {test_image_path}, creating a blank dummy image.")
            dummy_image = Image.new('RGB', (800, 1000), color = 'white')
    except ImportError: # In case Pillow is not available in a minimal test env
        print("Pillow (PIL) is not available. Cannot create/load dummy image for testing.")
        dummy_image = None
    except FileNotFoundError:
        print(f"Test image not found at {test_image_path}, creating a blank dummy image.")
        dummy_image = Image.new('RGB', (800, 1000), color = 'white')


    if dummy_image and MODEL: # Check if model was initialized
        print(f"Detecting tables on dummy image (size: {dummy_image.size})...")
        detected_tables = detect_tables_on_page_image(dummy_image)
        
        if detected_tables:
            print(f"Found {len(detected_tables)} tables:")
            for table in detected_tables:
                print(f"  Label: {table['label']}, Score: {table['score']:.2f}, Box: {table['box']}")
        else:
            print("No tables detected on the dummy image or model not initialized properly.")
    elif not MODEL:
        print("Model not initialized. Skipping detection test.")
    else:
        print("Dummy image not available. Skipping detection test.")
    
    print("ml_table_detector.py test finished.")