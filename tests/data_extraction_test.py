import unittest
import re
from dateutil import parser

# Data extraction and verification functions
def extract_date(text):
    try:
        date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})|(\w+ \d{1,2}, \d{4})|(\d{1,2} \w+ \d{4})', text, re.IGNORECASE)
        if date_match:
            date_str = date_match.group(0)
            date_obj = parser.parse(date_str)
            return date_obj.strftime('%Y-%m-%d')
        return None
    except Exception as e:
        print(f"  Error parsing date: {e}")
        return None

def verify_dates(start_date, end_date):
    if start_date and end_date:
        return end_date > start_date
    return False

def extract_policy_number(text):
    policy_number_match = re.search(r'[A-Z0-9]{8,}', text)
    if policy_number_match:
        return policy_number_match.group(0)
    return None

class TestDataExtraction(unittest.TestCase):
    def test_extract_date(self):
        self.assertEqual(extract_date("Policy Date: 01/01/2025"), "2025-01-01")
        self.assertEqual(extract_date("Policy Date: 1-1-2025"), "2025-01-01")
        self.assertEqual(extract_date("Policy Date: 01/01/25"), "2025-01-01")
        self.assertEqual(extract_date("Policy Date: 1/1/25"), "2025-01-01")
        self.assertEqual(extract_date("Policy Date: January 1, 2025"), "2025-01-01")
        self.assertEqual(extract_date("Policy Date: Jan 1, 2025"), "2025-01-01")
        self.assertEqual(extract_date("No date here"), None)

    def test_extract_date_new_format(self):
        self.assertEqual(extract_date("Policy Date: January 1, 2025"), "2025-01-01")

    def test_verify_dates(self):
        self.assertTrue(verify_dates("2024-01-01", "2025-01-01"))
        self.assertFalse(verify_dates("2025-01-01", "2024-01-01"))
        self.assertFalse(verify_dates(None, "2024-01-01"))
        self.assertFalse(verify_dates("2025-01-01", None))

    def test_extract_policy_number(self):
        self.assertEqual(extract_policy_number("Policy Number: ABC12345678"), "ABC12345678")
        self.assertEqual(extract_policy_number("Policy Number: ABC1234"), None)
        self.assertEqual(extract_policy_number("No policy number here"), None)

if __name__ == '__main__':
    unittest.main()