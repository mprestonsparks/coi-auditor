#!/usr/bin/env python3
"""
Comprehensive environment variable investigation script.
This script analyzes the discrepancies between .env and .env.example files
and tests the configuration system thoroughly.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def analyze_env_files():
    """Compare .env and .env.example files to identify discrepancies."""
    print("=" * 80)
    print("🔍 ENVIRONMENT FILE ANALYSIS")
    print("=" * 80)
    
    project_root = Path(__file__).resolve().parent
    env_path = project_root / '.env'
    env_example_path = project_root / '.env.example'
    
    # Read .env file
    env_vars = {}
    if env_path.exists():
        print(f"✅ Found .env file: {env_path}")
        content = env_path.read_text(encoding='utf-8')
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
        print(f"📊 Variables in .env: {len(env_vars)}")
        for key in sorted(env_vars.keys()):
            print(f"   • {key}")
    else:
        print(f"❌ .env file not found: {env_path}")
    
    # Read .env.example file
    example_vars = {}
    if env_example_path.exists():
        print(f"\n✅ Found .env.example file: {env_example_path}")
        content = env_example_path.read_text(encoding='utf-8')
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                example_vars[key.strip()] = value.strip()
        print(f"📊 Variables in .env.example: {len(example_vars)}")
        for key in sorted(example_vars.keys()):
            print(f"   • {key}")
    else:
        print(f"❌ .env.example file not found: {env_example_path}")
    
    # Compare files
    print(f"\n🔍 COMPARISON ANALYSIS")
    print("-" * 40)
    
    # Variables in .env but not in .env.example
    missing_from_example = set(env_vars.keys()) - set(example_vars.keys())
    if missing_from_example:
        print(f"❌ Variables in .env but MISSING from .env.example ({len(missing_from_example)}):")
        for var in sorted(missing_from_example):
            print(f"   • {var}")
    
    # Variables in .env.example but not in .env
    missing_from_env = set(example_vars.keys()) - set(env_vars.keys())
    if missing_from_env:
        print(f"❌ Variables in .env.example but MISSING from .env ({len(missing_from_env)}):")
        for var in sorted(missing_from_env):
            print(f"   • {var}")
    
    # Variables in both files
    common_vars = set(env_vars.keys()) & set(example_vars.keys())
    if common_vars:
        print(f"✅ Variables in BOTH files ({len(common_vars)}):")
        for var in sorted(common_vars):
            print(f"   • {var}")
    
    return env_vars, example_vars, missing_from_example, missing_from_env

def analyze_codebase_usage():
    """Search through codebase to find actual environment variable usage."""
    print("\n" + "=" * 80)
    print("🔍 CODEBASE ENVIRONMENT VARIABLE USAGE ANALYSIS")
    print("=" * 80)
    
    project_root = Path(__file__).resolve().parent
    src_dir = project_root / 'src'
    
    # Environment variables we're investigating
    target_vars = [
        'AUDIT_START_DATE', 'AUDIT_END_DATE', 'EXCEL_HEADER_ROW',
        'EXCEL_FILE_PATH', 'PDF_DIRECTORY_PATH', 'OUTPUT_DIRECTORY_PATH',
        'GL_FROM_COL', 'GL_TO_COL', 'WC_FROM_COL', 'WC_TO_COL',
        'POPPLER_BIN_PATH', 'TESSERACT_CMD'
    ]
    
    usage_found = {}
    
    for var in target_vars:
        usage_found[var] = []
        
        # Search through Python files
        for py_file in src_dir.rglob('*.py'):
            try:
                content = py_file.read_text(encoding='utf-8')
                if var in content:
                    # Find specific lines
                    lines = content.split('\n')
                    for i, line in enumerate(lines, 1):
                        if var in line:
                            usage_found[var].append({
                                'file': py_file.relative_to(project_root),
                                'line': i,
                                'content': line.strip()
                            })
            except Exception as e:
                logger.warning(f"Could not read {py_file}: {e}")
    
    # Report findings
    for var in target_vars:
        if usage_found[var]:
            print(f"\n✅ {var} - USED in codebase ({len(usage_found[var])} occurrences):")
            for usage in usage_found[var]:
                print(f"   📁 {usage['file']}:{usage['line']}")
                print(f"      {usage['content']}")
        else:
            print(f"\n❌ {var} - NOT FOUND in codebase")
    
    return usage_found

def test_configuration_loading():
    """Test the configuration loading system."""
    print("\n" + "=" * 80)
    print("🔍 CONFIGURATION LOADING TEST")
    print("=" * 80)
    
    try:
        # Add src to path
        project_root = Path(__file__).resolve().parent
        sys.path.insert(0, str(project_root / 'src'))
        
        # Load environment variables
        load_dotenv(project_root / '.env')
        
        # Test configuration loading
        from coi_auditor.config import load_config
        
        print("🔄 Loading configuration...")
        config = load_config()
        
        print("✅ Configuration loaded successfully!")
        print(f"📊 Configuration keys ({len(config)}):")
        for key in sorted(config.keys()):
            value = config[key]
            if isinstance(value, (str, int, float, bool)):
                print(f"   • {key}: {value}")
            else:
                print(f"   • {key}: {type(value).__name__}")
        
        return True, config
        
    except Exception as e:
        print(f"❌ Configuration loading failed: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def test_missing_variable_handling():
    """Test how the system handles missing environment variables."""
    print("\n" + "=" * 80)
    print("🔍 MISSING VARIABLE HANDLING TEST")
    print("=" * 80)
    
    # Test variables that should be required
    required_vars = [
        'AUDIT_START_DATE', 'AUDIT_END_DATE', 'EXCEL_FILE_PATH',
        'PDF_DIRECTORY_PATH', 'OUTPUT_DIRECTORY_PATH'
    ]
    
    # Save original values
    original_values = {}
    for var in required_vars:
        original_values[var] = os.getenv(var)
    
    try:
        # Test each variable individually
        for var in required_vars:
            print(f"\n🧪 Testing missing {var}...")
            
            # Temporarily remove the variable
            if var in os.environ:
                del os.environ[var]
            
            try:
                sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
                from coi_auditor.config import load_config
                
                # Try to reload the module to get fresh config
                import importlib
                import coi_auditor.config
                importlib.reload(coi_auditor.config)
                
                config = coi_auditor.config.load_config()
                print(f"❌ {var} missing but no error raised - this might be a problem!")
                
            except ValueError as e:
                if var in str(e):
                    print(f"✅ {var} missing correctly detected: {e}")
                else:
                    print(f"⚠️  {var} missing but different error: {e}")
            except Exception as e:
                print(f"⚠️  {var} missing caused unexpected error: {e}")
            
            # Restore the variable
            if original_values[var] is not None:
                os.environ[var] = original_values[var]
    
    finally:
        # Ensure all variables are restored
        for var, value in original_values.items():
            if value is not None:
                os.environ[var] = value

def generate_recommendations():
    """Generate recommendations for fixing the configuration system."""
    print("\n" + "=" * 80)
    print("📋 RECOMMENDATIONS")
    print("=" * 80)
    
    print("Based on the investigation, here are the key findings and recommendations:")
    print()
    
    print("1. 🔧 .env.example FILE NEEDS UPDATING:")
    print("   The .env.example file is severely outdated and missing most required variables.")
    print("   It should include all variables that are actually used by the application.")
    print()
    
    print("2. 📝 REQUIRED VARIABLES FOR .env.example:")
    required_for_example = [
        'AUDIT_START_DATE', 'AUDIT_END_DATE', 'EXCEL_HEADER_ROW',
        'EXCEL_FILE_PATH', 'PDF_DIRECTORY_PATH', 'OUTPUT_DIRECTORY_PATH',
        'GL_FROM_COL', 'GL_TO_COL', 'WC_FROM_COL', 'WC_TO_COL'
    ]
    print("   These variables are used in the codebase and should be in .env.example:")
    for var in required_for_example:
        print(f"   • {var}")
    print()
    
    print("3. 🔧 OPTIONAL VARIABLES:")
    optional_vars = ['POPPLER_BIN_PATH', 'TESSERACT_CMD']
    print("   These variables are optional and already in .env.example:")
    for var in optional_vars:
        print(f"   • {var}")
    print()
    
    print("4. 📋 CONFIGURATION STRATEGY:")
    print("   • Core paths and dates: Environment variables (.env)")
    print("   • Application settings: config.yaml")
    print("   • Optional system paths: Environment variables with defaults")
    print()
    
    print("5. 🛠️  IMMEDIATE ACTIONS NEEDED:")
    print("   • Update .env.example with all required variables")
    print("   • Add documentation for each variable")
    print("   • Ensure validation script checks all required variables")

def main():
    """Main investigation function."""
    print("🚀 COI AUDITOR ENVIRONMENT VARIABLE INVESTIGATION")
    print("This script will comprehensively analyze environment variable discrepancies")
    print("and test the configuration system.")
    print()
    
    # Step 1: Analyze environment files
    env_vars, example_vars, missing_from_example, missing_from_env = analyze_env_files()
    
    # Step 2: Analyze codebase usage
    usage_found = analyze_codebase_usage()
    
    # Step 3: Test configuration loading
    config_success, config = test_configuration_loading()
    
    # Step 4: Test missing variable handling
    test_missing_variable_handling()
    
    # Step 5: Generate recommendations
    generate_recommendations()
    
    print("\n" + "=" * 80)
    print("🎯 INVESTIGATION COMPLETE")
    print("=" * 80)
    
    return {
        'env_vars': env_vars,
        'example_vars': example_vars,
        'missing_from_example': missing_from_example,
        'missing_from_env': missing_from_env,
        'usage_found': usage_found,
        'config_success': config_success,
        'config': config
    }

if __name__ == "__main__":
    results = main()