import os
import importlib.util

surya_package_path = None
try:
    spec = importlib.util.find_spec("surya")
    if spec and spec.origin:
        surya_package_path = os.path.dirname(spec.origin)
        print(f"Found 'surya' package at: {surya_package_path}")
        
        print(f"\nContents of '{surya_package_path}':")
        for item in os.listdir(surya_package_path):
            print(f"  - {item}")
        
        ocr_subpackage_path = os.path.join(surya_package_path, "ocr")
        if os.path.exists(ocr_subpackage_path) and os.path.isdir(ocr_subpackage_path):
            print(f"\nContents of '{ocr_subpackage_path}':")
            for item in os.listdir(ocr_subpackage_path):
                print(f"  - {item} (is_file: {os.path.isfile(os.path.join(ocr_subpackage_path, item))})")
            
            # Check for __init__.py in surya.ocr
            ocr_init_path = os.path.join(ocr_subpackage_path, "__init__.py")
            if os.path.exists(ocr_init_path):
                print(f"\nFound: {ocr_init_path}")
                # Optionally, you could try to read a few lines if the tool allows
            else:
                print(f"\nWARNING: Did NOT find {ocr_init_path}. This would explain 'No module named surya.ocr' if 'ocr' is a directory.")
                
        else:
            print(f"\nWARNING: Subdirectory '{ocr_subpackage_path}' does not exist or is not a directory.")
            # Check if there's an ocr.py file instead
            ocr_file_path = os.path.join(surya_package_path, "ocr.py")
            if os.path.exists(ocr_file_path) and os.path.isfile(ocr_file_path):
                 print(f"\nFound an 'ocr.py' file instead: {ocr_file_path}")
            else:
                print(f"\nAlso did NOT find an 'ocr.py' file in {surya_package_path}")

    else:
        print("ERROR: Could not find 'surya' package spec. Is surya-ocr installed correctly?")

except Exception as e:
    print(f"An error occurred: {e}")