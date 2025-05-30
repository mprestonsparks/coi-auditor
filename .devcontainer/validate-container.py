#!/usr/bin/env python3
"""
Validation script for COI Auditor dev container setup.
This script verifies that all dependencies and tools are properly installed.
"""

import sys
import subprocess
import importlib
import os
from pathlib import Path


def check_python_version():
    """Check Python version."""
    print("🐍 Checking Python version...")
    version = sys.version_info
    print(f"   Python {version.major}.{version.minor}.{version.micro}")
    
    if version.major == 3 and version.minor >= 8:
        print("   ✅ Python version is compatible")
        return True
    else:
        print("   ❌ Python version should be 3.8 or higher")
        return False


def check_system_tools():
    """Check system dependencies."""
    print("\n🔧 Checking system tools...")
    tools = {
        'tesseract': ['tesseract', '--version'],
        'poppler': ['pdfinfo', '-v'],
        'git': ['git', '--version']
    }
    
    all_good = True
    for tool_name, command in tools.items():
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"   ✅ {tool_name} is available")
            else:
                print(f"   ❌ {tool_name} failed to run")
                all_good = False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print(f"   ❌ {tool_name} not found")
            all_good = False
    
    return all_good


def check_python_packages():
    """Check Python package imports."""
    print("\n📦 Checking Python packages...")
    
    # Core dependencies from pyproject.toml
    packages = [
        'openpyxl',
        'pdfplumber', 
        'dotenv',
        'pytesseract',
        'paddleocr',
        'rich',
        'tqdm',
        'pdf2image',
        'cv2',  # opencv-python
        'rapidfuzz',
        'yaml',  # PyYAML
        'dateutil',  # python-dateutil
        'numpy',
        'thefuzz',
        'skimage',  # scikit-image
        'transformers',
        'torch',
        'PIL',  # Pillow
        'timm'
    ]
    
    # Development dependencies
    dev_packages = [
        'invoke',
        'black',
        'pyright'
    ]
    
    all_packages = packages + dev_packages
    failed_imports = []
    
    for package in all_packages:
        try:
            importlib.import_module(package)
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} - import failed")
            failed_imports.append(package)
    
    if failed_imports:
        print(f"\n   Failed imports: {', '.join(failed_imports)}")
        return False
    
    return True


def check_environment_variables():
    """Check environment variables."""
    print("\n🌍 Checking environment variables...")
    
    required_vars = {
        'POPPLER_BIN_PATH': '/usr/bin',
        'TESSERACT_CMD': '/usr/bin/tesseract',
        'PYTHONPATH': '/workspace/src'
    }
    
    all_good = True
    for var_name, expected_value in required_vars.items():
        actual_value = os.environ.get(var_name)
        if actual_value:
            if actual_value == expected_value:
                print(f"   ✅ {var_name}={actual_value}")
            else:
                print(f"   ⚠️  {var_name}={actual_value} (expected: {expected_value})")
        else:
            print(f"   ❌ {var_name} not set")
            all_good = False
    
    return all_good


def check_project_structure():
    """Check project structure."""
    print("\n📁 Checking project structure...")
    
    expected_files = [
        'pyproject.toml',
        'config.yaml',
        '.env.example',
        'src/coi_auditor/__init__.py',
        'src/coi_auditor/main.py',
        'tests/',
        '.devcontainer/devcontainer.json',
        '.devcontainer/Dockerfile'
    ]
    
    workspace = Path('/workspace')
    all_good = True
    
    for file_path in expected_files:
        full_path = workspace / file_path
        if full_path.exists():
            print(f"   ✅ {file_path}")
        else:
            print(f"   ❌ {file_path} not found")
            all_good = False
    
    return all_good


def check_coi_auditor_installation():
    """Check if COI Auditor is properly installed."""
    print("\n🔍 Checking COI Auditor installation...")
    
    try:
        # Try importing the main module
        import coi_auditor
        print("   ✅ coi_auditor module can be imported")
        
        # Check if command line tool is available
        result = subprocess.run(['coi-auditor', '--help'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("   ✅ coi-auditor command is available")
            return True
        else:
            print("   ❌ coi-auditor command failed")
            return False
            
    except ImportError:
        print("   ❌ coi_auditor module import failed")
        return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("   ❌ coi-auditor command not found")
        return False


def main():
    """Run all validation checks."""
    print("🚀 COI Auditor Dev Container Validation")
    print("=" * 50)
    
    checks = [
        check_python_version,
        check_system_tools,
        check_environment_variables,
        check_project_structure,
        check_python_packages,
        check_coi_auditor_installation
    ]
    
    results = []
    for check in checks:
        try:
            result = check()
            results.append(result)
        except Exception as e:
            print(f"   ❌ Check failed with error: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print("📊 Validation Summary")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"🎉 All checks passed! ({passed}/{total})")
        print("\n✨ Your dev container is ready for COI Auditor development!")
        return 0
    else:
        print(f"⚠️  {passed}/{total} checks passed")
        print("\n🔧 Please review the failed checks above and rebuild the container if needed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())