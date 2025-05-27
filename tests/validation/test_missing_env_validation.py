#!/usr/bin/env python3
"""
Test script to validate that missing environment variables are properly detected.
This addresses the issue found where missing required variables don't raise errors.
"""

import os
import sys
import tempfile
from pathlib import Path
from dotenv import load_dotenv

def test_missing_env_detection():
    """Test that missing environment variables are properly detected."""
    print("🧪 TESTING MISSING ENVIRONMENT VARIABLE DETECTION")
    print("=" * 60)
    
    # Create a temporary .env file without required variables
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as temp_env:
        temp_env.write("# Minimal .env file for testing\n")
        temp_env.write("SOME_OTHER_VAR=test\n")
        temp_env_path = temp_env.name
    
    try:
        # Clear existing environment variables
        required_vars = [
            'AUDIT_START_DATE', 'AUDIT_END_DATE', 'EXCEL_FILE_PATH',
            'PDF_DIRECTORY_PATH', 'OUTPUT_DIRECTORY_PATH'
        ]
        
        original_values = {}
        for var in required_vars:
            original_values[var] = os.getenv(var)
            if var in os.environ:
                del os.environ[var]
        
        # Load the minimal .env file
        load_dotenv(dotenv_path=temp_env_path, override=True)
        
        # Add src to path
        project_root = Path(__file__).resolve().parent
        sys.path.insert(0, str(project_root / 'src'))
        
        # Try to load configuration
        try:
            from coi_auditor.config import load_config
            config = load_config()
            print("❌ CRITICAL ISSUE: Configuration loaded without required variables!")
            print("   This indicates the validation is not working properly.")
            return False
            
        except ValueError as e:
            print(f"✅ GOOD: Missing variables properly detected: {e}")
            return True
            
        except Exception as e:
            print(f"⚠️  UNEXPECTED ERROR: {e}")
            return False
            
    finally:
        # Restore original environment variables
        for var, value in original_values.items():
            if value is not None:
                os.environ[var] = value
        
        # Clean up temp file
        os.unlink(temp_env_path)

def test_validation_mode():
    """Test that validation mode properly relaxes path requirements."""
    print("\n🧪 TESTING VALIDATION MODE")
    print("=" * 60)
    
    # Set validation mode
    os.environ['COI_VALIDATION_MODE'] = '1'
    
    # Create a temporary .env file with only dates
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as temp_env:
        temp_env.write("# Validation mode .env file\n")
        temp_env.write("AUDIT_START_DATE=2023-01-01\n")
        temp_env.write("AUDIT_END_DATE=2023-12-31\n")
        temp_env_path = temp_env.name
    
    try:
        # Clear path-related environment variables
        path_vars = ['EXCEL_FILE_PATH', 'PDF_DIRECTORY_PATH', 'OUTPUT_DIRECTORY_PATH']
        original_values = {}
        for var in path_vars:
            original_values[var] = os.getenv(var)
            if var in os.environ:
                del os.environ[var]
        
        # Load the validation .env file
        load_dotenv(dotenv_path=temp_env_path, override=True)
        
        # Add src to path
        project_root = Path(__file__).resolve().parent
        sys.path.insert(0, str(project_root / 'src'))
        
        # Try to load configuration
        try:
            from coi_auditor.config import load_config
            config = load_config()
            print("✅ GOOD: Configuration loaded in validation mode without path variables")
            return True
            
        except Exception as e:
            print(f"❌ ISSUE: Validation mode failed: {e}")
            return False
            
    finally:
        # Restore original environment variables
        for var, value in original_values.items():
            if value is not None:
                os.environ[var] = value
        
        # Remove validation mode
        if 'COI_VALIDATION_MODE' in os.environ:
            del os.environ['COI_VALIDATION_MODE']
        
        # Clean up temp file
        os.unlink(temp_env_path)

def test_date_validation():
    """Test that invalid date formats are properly detected."""
    print("\n🧪 TESTING DATE VALIDATION")
    print("=" * 60)
    
    test_cases = [
        ("invalid-date", "2023-12-31", "Invalid start date format"),
        ("2023-01-01", "invalid-date", "Invalid end date format"),
        ("2023-12-31", "2023-01-01", "Start date after end date"),
        ("2023-01-01", "2023-12-31", "Valid dates")
    ]
    
    for start_date, end_date, description in test_cases:
        print(f"\n🔍 Testing: {description}")
        
        # Create temporary .env file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as temp_env:
            temp_env.write(f"AUDIT_START_DATE={start_date}\n")
            temp_env.write(f"AUDIT_END_DATE={end_date}\n")
            temp_env.write("EXCEL_FILE_PATH=tests/fixtures/test_subcontractors.xlsx\n")
            temp_env.write("PDF_DIRECTORY_PATH=tests/fixtures/\n")
            temp_env.write("OUTPUT_DIRECTORY_PATH=output/\n")
            temp_env_path = temp_env.name
        
        try:
            # Clear existing date variables
            original_start = os.getenv('AUDIT_START_DATE')
            original_end = os.getenv('AUDIT_END_DATE')
            
            if 'AUDIT_START_DATE' in os.environ:
                del os.environ['AUDIT_START_DATE']
            if 'AUDIT_END_DATE' in os.environ:
                del os.environ['AUDIT_END_DATE']
            
            # Load test .env file
            load_dotenv(dotenv_path=temp_env_path, override=True)
            
            # Add src to path
            project_root = Path(__file__).resolve().parent
            sys.path.insert(0, str(project_root / 'src'))
            
            # Try to load configuration
            try:
                from coi_auditor.config import load_config
                config = load_config()
                
                if description == "Valid dates":
                    print("   ✅ Valid dates accepted")
                else:
                    print(f"   ❌ ISSUE: Invalid dates were accepted: {description}")
                    
            except ValueError as e:
                if description == "Valid dates":
                    print(f"   ❌ ISSUE: Valid dates rejected: {e}")
                else:
                    print(f"   ✅ Invalid dates properly rejected: {e}")
                    
            except Exception as e:
                print(f"   ⚠️  Unexpected error: {e}")
                
        finally:
            # Restore original values
            if original_start is not None:
                os.environ['AUDIT_START_DATE'] = original_start
            if original_end is not None:
                os.environ['AUDIT_END_DATE'] = original_end
            
            # Clean up temp file
            os.unlink(temp_env_path)

def main():
    """Run all validation tests."""
    print("🚀 ENVIRONMENT VARIABLE VALIDATION TESTING")
    print("This script tests the robustness of environment variable validation.")
    print()
    
    results = []
    
    # Test 1: Missing variable detection
    results.append(test_missing_env_detection())
    
    # Test 2: Validation mode
    results.append(test_validation_mode())
    
    # Test 3: Date validation
    test_date_validation()
    
    print("\n" + "=" * 60)
    print("🎯 VALIDATION TESTING COMPLETE")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("✅ All validation tests passed!")
    else:
        print("❌ Some validation tests failed - configuration system needs fixes!")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)