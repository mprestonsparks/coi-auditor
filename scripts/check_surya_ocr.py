import sys
print("Current Python sys.path:")
for p in sys.path:
    print(p)
print("-" * 20)

try:
    # First, try to import the ocr module itself
    from surya.ocr import run_ocr
    print("SUCCESS: Module 'surya.ocr' imported successfully.")
    
    # Now, check if run_ocr is an attribute of this module
    #if hasattr(ocr, 'run_ocr'):
    #    run_ocr = getattr(ocr, 'run_ocr') # Get the run_ocr attribute
    #    print("SUCCESS: 'run_ocr' function is available and imported from surya.ocr.")
        # You could even print its type to be sure
        # print(type(run_ocr)) 
    #else:
    #    print("ERROR: 'run_ocr' function NOT found as an attribute in surya.ocr module.")
    #    print("Available attributes in surya.ocr:", dir(ocr))
    print("SUCCESS: 'run_ocr' function is available and imported from surya.ocr.")

except ImportError as e:
    print(f"FAIL: Failed to import 'surya.ocr' module. Error: {e}")
except Exception as e_gen:
    print(f"FAIL: An unexpected error occurred while trying to import or inspect surya.ocr: {e_gen}")