import pandas as pd

# Read the main Excel file
print("=== EXCEL SUMMARY SHEET ===")
df = pd.read_excel('tests/fixtures/test_subcontractors.xlsx', sheet_name='SUMMARY')
print(df.to_string())

print("\n=== CHECKING FOR GAPS_REPORT SHEET ===")
try:
    gaps_df = pd.read_excel('tests/fixtures/test_subcontractors.xlsx', sheet_name='GAPS_REPORT')
    print("GAPS_REPORT Sheet found:")
    print(gaps_df.head(10).to_string())
except Exception as e:
    print(f"No GAPS_REPORT sheet found: {e}")

print("\n=== SHEET NAMES ===")
xl_file = pd.ExcelFile('tests/fixtures/test_subcontractors.xlsx')
print("Available sheets:", xl_file.sheet_names)