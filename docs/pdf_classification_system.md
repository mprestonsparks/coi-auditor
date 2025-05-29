# PDF Classification System Documentation

## Overview

The PDF Classification System is a comprehensive, evidence-based framework that replaces the simple "Missing PDF" classification with a sophisticated four-state model. This system distinguishes between technical failures and legitimate business cases, providing actionable insights for different types of PDF-related issues.

## Classification States

### 1. VERIFIED
- **Description**: PDF exists and was successfully processed with dates extracted
- **Confidence**: High (typically 0.8-1.0)
- **Action**: None (for high confidence) or Review extraction quality (for lower confidence)
- **Report Destination**: Success Log or QA Report

### 2. UNVERIFIED  
- **Description**: No PDF found after exhaustive search (business issue - certificate not provided)
- **Confidence**: Variable based on search thoroughness
- **Action**: Request certificate (high confidence) or Manual investigation (low confidence)
- **Report Destination**: gaps_report or gaps_report + review_queue

### 3. TECHNICAL_FAILURE
- **Description**: PDF exists but couldn't be processed (technical issue)
- **Confidence**: Variable based on evidence strength
- **Action**: Fix technical issue (high confidence) or Investigate root cause (low confidence)
- **Report Destination**: errors_report or errors_report + diagnostics

### 4. ADMINISTRATIVE
- **Description**: Non-business entries (TOTALS, headers, etc.)
- **Confidence**: Always high (1.0)
- **Action**: Skip
- **Report Destination**: metadata_report

## Evidence Framework

The classification system uses four types of evidence:

### Direct Evidence
- PDF exists with exact name match
- PDF was successfully processed
- Dates were extracted from PDF
- Processing errors occurred

### Circumstantial Evidence
- Files with similar names exist (with similarity scores)
- Directory contains patterns matching subcontractor
- Name variations and fuzzy matching results
- Company pattern matches

### Negative Evidence
- No files found after exhaustive search
- All similar files belong to other subcontractors
- Directory accessibility and search thoroughness

### Meta Evidence
- Row contains non-business data (TOTALS, headers)
- Subcontractor name has administrative markers
- Numeric-only or very short names

## Confidence Calculation

Confidence scores range from 0.0 to 1.0 and are calculated using weighted evidence:

- **Direct Evidence**: 0.5 for PDF existence, 0.3 for processing, 0.2 for dates
- **Special Case**: PDF exists with processing errors → 0.8 confidence (clear technical failure)
- **Circumstantial Evidence**: 0.1-0.3 based on similarity scores
- **Negative Evidence**: 0.3-0.4 for thorough searches with no results
- **Meta Evidence**: Override to 1.0 for administrative entries

## Action Determination Matrix

| State | Confidence | Action | Report Destination |
|-------|------------|--------|-------------------|
| VERIFIED | High (≥0.8) | None | Success Log |
| VERIFIED | Low (<0.8) | Review extraction quality | QA Report |
| TECHNICAL_FAILURE | High (≥0.7) | Fix technical issue | errors_report |
| TECHNICAL_FAILURE | Low (<0.7) | Investigate root cause | errors_report + diagnostics |
| UNVERIFIED | High (≥0.7) | Request certificate | gaps_report |
| UNVERIFIED | Low (<0.7) | Manual investigation | gaps_report + review_queue |
| ADMINISTRATIVE | Any | Skip | metadata_report |
| UNKNOWN | Any | Manual review | review_queue |

## Administrative Entry Detection

The system automatically detects administrative entries using pattern matching:

### Detected Patterns
- `TOTAL`, `Sub-Total`, `GRAND TOTAL`
- `Header`, `Footer`, `Summary`
- Empty or whitespace-only entries
- `N/A`, `TBD`, `Pending`
- `Inactive`, `Terminated`, `Cancelled`, `Void`
- Numeric-only names (likely row numbers)
- Very short names (≤2 characters)

### Pattern Matching
- Case-insensitive regex patterns
- Exact matches for administrative terms
- Special handling for business names containing these terms

## Name Variation Generation

For fuzzy matching, the system generates multiple name variations:

### Variation Types
1. **Original name**: As provided
2. **Business suffix removal**: Remove LLC, Inc, Corp, Co, Ltd, LP, LLP, PC
3. **Punctuation handling**: 
   - Remove all punctuation
   - Replace punctuation with spaces
4. **Ampersand variations**:
   - Replace `&` with `and`
   - Replace `and` with `&`

### Example
```
Original: "Smith & Jones LLC"
Variations:
- "Smith & Jones LLC"
- "Smith & Jones"
- "Smith  Jones LLC"
- "Smith and Jones LLC"
```

## Integration Points

### Backward Compatibility
The system provides legacy status mapping:
- `VERIFIED` → `STATUS_OK`
- `UNVERIFIED` → `STATUS_MISSING_PDF`
- `TECHNICAL_FAILURE` → `STATUS_PDF_ERROR`
- `ADMINISTRATIVE` → `"ADMINISTRATIVE"` (new)

### Existing Code Integration
- Uses existing `find_coi_pdfs()` function
- Leverages existing `extract_dates_from_pdf()` function
- Compatible with current subcontractor data structure
- Works with existing fuzzy matching configuration

## API Reference

### Main Classification Function

```python
def classify_pdf_status(subcontractor: Dict[str, Any], pdf_directory: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Classify PDF status using evidence-based framework.
    
    Args:
        subcontractor: Dict with subcontractor data including 'name'
        pdf_directory: Path to directory containing PDF files
        config: Configuration object
    
    Returns:
        dict: {
            'state': str,           # Classification state
            'confidence': float,    # Confidence score (0.0-1.0)
            'evidence': dict,       # Collected evidence
            'action': str,          # Recommended action
            'report_destination': str  # Where to report this case
        }
    """
```

### Utility Functions

```python
def is_administrative_entry(subcontractor_name: str) -> bool:
    """Quick check if a subcontractor name represents an administrative entry."""

def get_classification_summary(classification_result: Dict[str, Any]) -> str:
    """Generate a human-readable summary of the classification result."""

def generate_diagnostic_record(subcontractor: Dict[str, Any], state: str, confidence: float, evidence: Dict[str, Any], action: str) -> Dict[str, Any]:
    """Generate comprehensive diagnostic record for non-verified subcontractors."""
```

## Usage Examples

### Basic Classification
```python
from coi_auditor.pdf_classifier import classify_pdf_status

subcontractor = {'name': 'ABC Construction LLC', 'id': '123'}
config = {'fuzzy_matching': {'enabled': True}}
pdf_directory = '/path/to/pdfs'

result = classify_pdf_status(subcontractor, pdf_directory, config)
print(f"State: {result['state']}, Confidence: {result['confidence']:.1%}")
```

### Administrative Check
```python
from coi_auditor.pdf_classifier import is_administrative_entry

if is_administrative_entry("TOTAL"):
    print("Skip this entry - it's administrative")
```

### Diagnostic Information
```python
from coi_auditor.pdf_classifier import generate_diagnostic_record

if result['state'] != 'VERIFIED':
    diagnostic = generate_diagnostic_record(
        subcontractor, result['state'], result['confidence'], 
        result['evidence'], result['action']
    )
    print("Manual review hints:", diagnostic['manual_review_hints'])
```

## Performance Considerations

### Optimization Features
- Early return for administrative entries (no PDF search needed)
- Cached file system operations where possible
- Limited similarity searches to reasonable bounds
- Graceful handling of permission errors

### Scalability
- Designed for batch processing of large subcontractor lists
- Memory-efficient evidence collection
- Configurable similarity thresholds to balance accuracy vs. performance

## Error Handling

### Robust Error Management
- Handles missing PDF directories gracefully
- Catches and logs PDF processing exceptions
- Provides meaningful error messages in evidence
- Continues processing even when individual PDFs fail

### Fallback Behavior
- Defaults to UNKNOWN state when classification is uncertain
- Provides diagnostic information for manual review
- Maintains evidence trail for debugging

## Testing

The system includes comprehensive tests covering:
- Administrative entry detection
- Name variation generation
- All four classification states
- Confidence calculation accuracy
- Error handling scenarios
- Integration with existing PDF processing

Run tests with:
```bash
python -m pytest tests/test_pdf_classifier.py -v
```

## Future Enhancements

### Potential Improvements
1. **Machine Learning Integration**: Train models on historical classification data
2. **Historical Context**: Use previous audit results to improve classification
3. **Company Relationship Mapping**: Detect related companies/subsidiaries
4. **Advanced Fuzzy Matching**: Implement phonetic matching algorithms
5. **Performance Metrics**: Track classification accuracy over time

### Configuration Extensions
- Customizable administrative patterns
- Adjustable confidence thresholds
- Configurable similarity scoring weights
- Custom action determination rules

## Conclusion

The PDF Classification System provides a robust, evidence-based approach to categorizing subcontractor PDF status. By distinguishing between technical failures and business issues, it enables more targeted remediation efforts and improves overall audit efficiency.

The system is designed for easy integration with existing code while providing comprehensive diagnostic capabilities for complex cases requiring manual review.