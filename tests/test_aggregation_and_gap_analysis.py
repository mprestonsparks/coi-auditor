import os
from dotenv import load_dotenv
import openpyxl
from coi_auditor.pdf_parser import extract_dates_from_pdf
from coi_auditor.audit import aggregate_dates, check_coverage_gap

def test_aggregation_and_gap_analysis():
    # .env file is in the project root, one level up from the 'tests' directory
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dotenv_path = os.path.join(project_root, '.env')
    load_dotenv(dotenv_path=dotenv_path)

    # Use a fixture PDF
    fixtures_dir = os.path.join(project_root, 'tests', 'fixtures')
    # Choose a fixture known to have extractable dates
    sample_pdf_name = 'FernandoHernandez_2024-09-19.pdf'
    pdf_path = os.path.join(fixtures_dir, sample_pdf_name)
    assert os.path.exists(pdf_path), f"Fixture PDF not found: {pdf_path}"

    from datetime import datetime, date # Ensure date is imported

    try:
        print(f"Testing aggregation and gap analysis with PDF: {sample_pdf_name}")
        # extract_dates_from_pdf returns: Tuple[Dict[str, Optional[date]], str]
        extracted_dates_dict, note_from_parser = extract_dates_from_pdf(pdf_path)

        if not extracted_dates_dict and not note_from_parser:
            print(f"No dates or notes extracted from {sample_pdf_name}. Cannot proceed with test.")
            # Consider an assertion failure here if dates are expected from this fixture
            assert False, f"Fixture {sample_pdf_name} did not yield dates or notes."
            return

        # aggregate_dates expects: List[Tuple[str, Tuple[Dict[str, Optional[date]], str]]]
        # So, the second element of the outer tuple must be (dates_dict, note_string)
        all_pdf_results_for_aggregation = [(str(pdf_path), (extracted_dates_dict, note_from_parser))]
        
        aggregated_dates, aggregated_notes = aggregate_dates(all_pdf_results_for_aggregation)
        
        print(f"Extracted from PDF: {extracted_dates_dict}, Note: '{note_from_parser}'")
        print(f"Aggregated Dates: {aggregated_dates}")
        print(f"Aggregated Notes: {aggregated_notes}")

        # Test gap analysis for GL (assuming fixture has GL dates)
        audit_start_str = os.getenv('AUDIT_START_DATE')
        audit_end_str = os.getenv('AUDIT_END_DATE')

        assert audit_start_str, "AUDIT_START_DATE not set in .env"
        assert audit_end_str, "AUDIT_END_DATE not set in .env"

        audit_start_date = datetime.strptime(audit_start_str, '%Y-%m-%d').date()
        audit_end_date = datetime.strptime(audit_end_str, '%Y-%m-%d').date()

        gl_from_date = aggregated_dates.get('gl_from')
        gl_to_date = aggregated_dates.get('gl_to')

        if gl_from_date and gl_to_date:
            gap_status, gap_details = check_coverage_gap(gl_from_date, gl_to_date, audit_start_date, audit_end_date)
            print(f"GL Gap Status: {gap_status} | Details: {gap_details}")
            # Add assertions here based on expected outcome for the fixture
            # e.g., assert gap_status == "OK", f"Gap detected unexpectedly for GL in {sample_pdf_name}: {gap_details}"
        else:
            print(f"GL dates not found in aggregated results for {sample_pdf_name}, skipping GL gap check.")
            # If GL dates are expected from this fixture, this could be an assertion failure:
            # assert False, f"Expected GL dates from {sample_pdf_name}, but none found in aggregated results."


        # Similar check for WC if applicable for the fixture
        wc_from_date = aggregated_dates.get('wc_from')
        wc_to_date = aggregated_dates.get('wc_to')
        if wc_from_date and wc_to_date:
            gap_status_wc, gap_details_wc = check_coverage_gap(wc_from_date, wc_to_date, audit_start_date, audit_end_date)
            print(f"WC Gap Status: {gap_status_wc} | Details: {gap_details_wc}")
            # Add assertions here based on expected outcome for the fixture
            # e.g., assert gap_status_wc == "OK", f"Gap detected unexpectedly for WC in {sample_pdf_name}: {gap_details_wc}"
        else:
            print(f"WC dates not found in aggregated results for {sample_pdf_name}, skipping WC gap check.")
            # If WC dates are expected, assert False here too.

        print("test_aggregation_and_gap_analysis PASSED (inspect output for correctness and add specific assertions)")

    except Exception as e:
        print(f"Error during test_aggregation_and_gap_analysis: {e}")
        raise # Re-raise to fail the test clearly

if __name__ == '__main__':
    test_aggregation_and_gap_analysis()
