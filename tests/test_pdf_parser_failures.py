import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.coi_auditor.pdf_parser import reconcile_layout_regions

def test_reconcile_layout_regions_no_tables_no_columns():
    """
    Test case where there are no tables and no columns detected.
    This test should fail because the current implementation returns a list with one element,
    but it should return an empty list.
    """
    detected_columns = []
    detected_tables = []
    page_width = 612
    page_height = 792
    config = {}
    debug_mode = False

    result = reconcile_layout_regions(
        detected_columns, detected_tables, page_width, page_height, config, debug_mode
    )

    assert len(result) == 0, "Expected an empty list when no tables or columns are detected."


def test_reconcile_layout_regions_one_table_incorrect_bbox():
    """
    Test case where there is one table detected, but the bounding box is incorrect.
    This test should fail because the current implementation does not correctly handle
    the bounding box normalization.
    """
    detected_columns = []
    # Intentionally provide a bbox that will be different after normalization
    detected_tables = [{"box": [100.123, 100.456, 200.789, 200.321]}] 
    page_width = 612
    page_height = 792
    config = {}
    debug_mode = False

    result = reconcile_layout_regions(
        detected_columns, detected_tables, page_width, page_height, config, debug_mode
    )

    assert len(result) == 1
    assert result[0]["type"] == "table"
    # This assertion will likely fail due to floating point precision issues or incorrect normalization
    assert result[0]["bbox"] == [
        100 / page_width, 
        100 / page_height,
        200 / page_width,
        200 / page_height,
    ], "Bounding box normalization is incorrect."


def test_reconcile_layout_regions_column_partially_covered_by_table():
    """
    Test case where a column is partially covered by a table.
    This test should fail if the column fragment is not correctly calculated.
    """
    # Column covers the whole page
    detected_columns = [(0.0, 0.0, 612.0, 792.0)]
    # Table covers the center of the page
    detected_tables = [{"box": [100.0, 100.0, 200.0, 200.0]}]
    page_width = 612
    page_height = 792
    config = {}
    debug_mode = False

    result = reconcile_layout_regions(
        detected_columns, detected_tables, page_width, page_height, config, debug_mode
    )
    
    # This assertion is likely to fail if the subtraction logic is flawed
    # or if too many/few fragments are created.
    assert len(result) > 1, "Expected multiple regions when a column is split by a table."
    
    table_region_found = any(r['type'] == 'table' for r in result)
    assert table_region_found, "Table region should be present in the result."

    column_fragment_found = any(r['type'] == 'column_fragment' for r in result)
    assert column_fragment_found, "Column fragment(s) should be present in the result."