# Fuzzy Matching Implementation for COI Auditor

## Overview

This document describes the implementation of fuzzy matching capabilities for the COI Auditor PDF discovery system to resolve "Missing PDF" errors. The implementation uses the `rapidfuzz` library to provide intelligent matching when exact string matching fails.

## Key Features Implemented

### 1. Enhanced Name Normalization

- **Function**: `_normalize_name_enhanced()`
- **Purpose**: Preserves business terms while normalizing names for better matching
- **Features**:
  - Preserves business terms like LLC, Inc, Corp, Construction, etc.
  - Handles common punctuation and spacing variations
  - Configurable business terms mapping via `config.yaml`

### 2. Name Variation Generation

- **Function**: `_get_normalized_variations()`
- **Purpose**: Generates multiple normalized variations of a name for comprehensive matching
- **Features**:
  - Creates variations with and without business suffixes
  - Generates space-removed variations
  - Maintains backward compatibility with simple normalization

### 3. Fuzzy Matching Algorithm

- **Function**: `find_best_fuzzy_matches()`
- **Purpose**: Performs fuzzy matching using multiple algorithms
- **Features**:
  - Uses rapidfuzz library with multiple scoring algorithms:
    - `ratio`: Basic string similarity
    - `partial_ratio`: Partial string matching
    - `token_sort_ratio`: Token-based matching with sorting
  - Configurable similarity threshold (default: 75.0%)
  - Returns top matches sorted by score
  - Comprehensive logging for debugging

### 4. Integrated PDF Discovery

- **Function**: `find_coi_pdfs()` (enhanced)
- **Purpose**: Uses fuzzy matching as fallback when exact matches fail
- **Features**:
  - Maintains exact matching as primary method
  - Falls back to fuzzy matching when no exact matches found
  - Configurable via `fuzzy_matching` section in config
  - Preserves all existing functionality

## Configuration

### Added to `config.yaml`:

```yaml
# Fuzzy Matching Settings for PDF Discovery
fuzzy_matching:
  enabled: true # Enable fuzzy matching as fallback when exact matches fail
  threshold: 75.0 # Similarity threshold (0-100 scale) for fuzzy matching
  max_results: 5 # Maximum number of fuzzy match results to return
  algorithms:
    - "ratio" # Basic string similarity
    - "partial_ratio" # Partial string matching
    - "token_sort_ratio" # Token-based matching with sorting

# Name Normalization Settings
name_normalization:
  # Business terms that should be preserved during normalization
  business_terms:
    "llc": "llc"
    "inc": "inc"
    "corp": "corp"
    "corporation": "corp"
    "company": "company"
    "co": "co"
    "ltd": "ltd"
    "limited": "ltd"
    "construction": "construction"
    "contracting": "contracting"
    "contractors": "contractors"
    "services": "services"
    "group": "group"
    "enterprises": "enterprises"
    "solutions": "solutions"
  # Additional variations to generate for better matching
  generate_variations: true
```

## Dependencies

### Added to `pyproject.toml`:

```toml
"rapidfuzz>=3.6.0" # Added for fuzzy matching capabilities
```

## Integration Points

### 1. PDF Parser (`src/coi_auditor/pdf_parser.py`)

- Added rapidfuzz import with fallback handling
- Implemented enhanced normalization functions
- Added fuzzy matching algorithm
- Enhanced `find_coi_pdfs()` function with fuzzy matching fallback

### 2. Audit Module (`src/coi_auditor/audit.py`)

- Updated `process_subcontractor()` to pass fuzzy matching configuration
- Maintains backward compatibility with existing workflow

## Usage Examples

### Basic Usage (Automatic)

The fuzzy matching is automatically enabled as a fallback when exact matches fail:

```python
# This will try exact matching first, then fuzzy matching if needed
found_pdfs = find_coi_pdfs(
    pdf_directory_path="/path/to/pdfs",
    subcontractor_name="31-W Insulation"
)
```

### Custom Configuration

```python
# Custom fuzzy matching parameters
fuzzy_config = {
    'enabled': True,
    'threshold': 80.0,  # Higher threshold for stricter matching
    'max_results': 3
}

found_pdfs = find_coi_pdfs(
    pdf_directory_path="/path/to/pdfs",
    subcontractor_name="31-W Insulation",
    fuzzy_config=fuzzy_config
)
```

## Test Results

The implementation has been thoroughly tested and shows excellent results:

### Name Normalization Examples:
- "31-W Insulation" → "31winsulation"
- "Sainz Construction LLC" → ["sainzconstructionllc", "sainzconstruction"]
- "S&G Siding and Gutters" → "sgsidingandgutters"

### Fuzzy Matching Examples:
- "31-W Insulation" matches "31-W Insulation_2023-11-06" (100% score)
- "31W Insulation" matches "31-W Insulation_2023-11-06" (100% score)
- "Fernando Hernandez" matches "FernandoHernandez_2024-09-19" (100% score)

### Test Coverage:
- ✅ All existing tests pass (backward compatibility maintained)
- ✅ Fuzzy matching tests pass
- ✅ End-to-end validation tests pass
- ✅ PDF discovery integration tests pass

## Error Handling

- Graceful fallback when rapidfuzz library is not available
- Comprehensive logging for debugging matching process
- Maintains existing error handling patterns
- No breaking changes to existing functionality

## Performance Considerations

- Fuzzy matching only activates when exact matching fails
- Configurable result limits to prevent excessive processing
- Efficient normalization with caching of variations
- Minimal overhead when fuzzy matching is disabled

## Future Enhancements

Potential areas for future improvement:
1. Machine learning-based similarity scoring
2. Industry-specific business term recognition
3. Phonetic matching algorithms
4. Performance optimization for large PDF directories
5. Advanced configuration options for different matching strategies

## Conclusion

The fuzzy matching implementation successfully addresses the "Missing PDF" errors while maintaining full backward compatibility. The system now provides intelligent fallback matching that can handle common variations in subcontractor names, significantly improving PDF discovery success rates.