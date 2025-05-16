"""Loads configuration from the .env file."""

import os
from dotenv import load_dotenv
from datetime import datetime
import logging
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_config():
    """Load configuration from config.yaml and .env file."""
    is_validation_mode = os.getenv('COI_VALIDATION_MODE') == '1'
    if is_validation_mode:
        # Use the logger instance from the module if available, or basicConfig if not yet fully set up.
        # Assuming basicConfig is sufficient here as this is early in config load.
        logging.info("COI_VALIDATION_MODE is active. Path requirements (EXCEL_FILE_PATH, PDF_DIRECTORY_PATH, OUTPUT_DIRECTORY_PATH) will be relaxed.")

    # Determine the project root directory.
    # config.py is located at project_root/src/coi_auditor/config.py
    # To get project_root, we need to go up three levels from __file__.
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    config = {}

    # 1. Load from config.yaml (base configuration)
    yaml_config_path = os.path.join(project_root, 'config.yaml')
    if os.path.exists(yaml_config_path):
        try:
            with open(yaml_config_path, 'r', encoding='utf-8') as f:
                yaml_data = yaml.safe_load(f)
                if yaml_data:
                    config.update(yaml_data)
                    logging.info(f"Loaded base configuration from: {yaml_config_path}")
                else:
                    logging.warning(f"config.yaml at {yaml_config_path} is empty. No YAML configuration loaded.")
        except yaml.YAMLError as e:
            logging.error(f"Error parsing YAML from {yaml_config_path}: {e}")
        except Exception as e:
            logging.error(f"Could not read or process {yaml_config_path}: {e}")
    else:
        logging.warning(
            f"config.yaml not found at {yaml_config_path}. "
            "Proceeding without YAML-based configuration. "
            "New features requiring config.yaml may not function correctly or use defaults."
        )

    # 2. Load from .env file (can override YAML or add .env-specific settings)
    dotenv_path_project_root = os.path.join(project_root, '.env')
    dotenv_path_cwd = os.path.join(os.getcwd(), '.env')

    actual_dotenv_path = None
    if os.path.exists(dotenv_path_project_root):
        actual_dotenv_path = dotenv_path_project_root
    elif os.path.exists(dotenv_path_cwd):
        actual_dotenv_path = dotenv_path_cwd
        logging.info(f".env not found in project root ({project_root}), using .env from current working directory: {dotenv_path_cwd}")
    
    if actual_dotenv_path:
        load_dotenv(dotenv_path=actual_dotenv_path, override=True)
        logging.info(f"Loaded .env variables from: {actual_dotenv_path}. These can override config.yaml settings.")
    else:
        logging.warning(
            f".env file not found in project root ({dotenv_path_project_root}) or CWD ({dotenv_path_cwd}). "
            "Relying on environment variables already set in the shell, or values from config.yaml."
        )

    # Populate/override config from environment variables for specific, known keys
    env_vars_to_map = {
        'excel_file_path': 'EXCEL_FILE_PATH',
        'pdf_directory_path': 'PDF_DIRECTORY_PATH',
        'output_directory_path': 'OUTPUT_DIRECTORY_PATH',
    }

    for config_key, env_var_key in env_vars_to_map.items():
        env_value = os.getenv(env_var_key)
        if env_value is not None:
            config[config_key] = env_value # .env overrides if present

    # Handle dates specifically from .env (as they need parsing and validation)
    audit_start_date_env = os.getenv('AUDIT_START_DATE')
    audit_end_date_env = os.getenv('AUDIT_END_DATE')

    if audit_start_date_env:
        config['audit_start_date_str_from_env'] = audit_start_date_env
    if audit_end_date_env:
        config['audit_end_date_str_from_env'] = audit_end_date_env
    
    # --- Validation of critical .env-expected variables ---
    # Path-related keys that are optional in validation mode
    optional_if_validation_mode_keys = {
        'excel_file_path': 'EXCEL_FILE_PATH',
        'pdf_directory_path': 'PDF_DIRECTORY_PATH',
        'output_directory_path': 'OUTPUT_DIRECTORY_PATH',
    }
    # Date-related keys are always required
    always_required_keys = {
        'audit_start_date_str_from_env': 'AUDIT_START_DATE', # Check for the string version from .env
        'audit_end_date_str_from_env': 'AUDIT_END_DATE',   # Check for the string version from .env
    }

    missing_vars = []

    # Check path variables
    for conf_key, env_name in optional_if_validation_mode_keys.items():
        if conf_key not in config or config[conf_key] is None:
            if not is_validation_mode: # Only required if not in validation mode
                missing_vars.append(env_name)
            else:
                logging.info(f"Validation mode: Optional var '{env_name}' not found or not set, proceeding.")
    
    # Check date variables (always required)
    # These are checked based on the keys used to store them after os.getenv
    if 'audit_start_date_str_from_env' not in config:
        missing_vars.append('AUDIT_START_DATE')
    if 'audit_end_date_str_from_env' not in config:
        missing_vars.append('AUDIT_END_DATE')

    if missing_vars:
        raise ValueError(f"Missing required environment variable(s) or .env entries: {', '.join(missing_vars)}")

    # Convert paths to absolute paths
    for path_key in ['excel_file_path', 'pdf_directory_path', 'output_directory_path']:
        if path_key in config and config[path_key]: # Ensure key exists and is not None
            config[path_key] = os.path.abspath(config[path_key])

    # Ensure output directory exists if it's configured
    output_dir = config.get('output_directory_path') # Will be None if not set
    
    if output_dir: # Only proceed if output_dir has a value (i.e., it was configured)
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
                logging.info(f"Created output directory: {output_dir}")
            except OSError as e:
                # If not in validation mode, this is a fatal error.
                # If in validation mode, this path is optional, so a warning is sufficient if provided but fails.
                if not is_validation_mode:
                    raise ValueError(f"Could not create configured output directory: {output_dir}. Error: {e}")
                else:
                    logging.warning(f"Validation mode: Could not create (optionally provided) output directory '{output_dir}'. Error: {e}")
        elif not os.path.isdir(output_dir):
            if not is_validation_mode:
                raise ValueError(f"Configured output directory path exists but is not a directory: {output_dir}")
            else:
                logging.warning(f"Validation mode: (Optionally provided) output directory path '{output_dir}' exists but is not a directory.")
    elif not is_validation_mode:
        # This case means output_dir is None AND we are NOT in validation mode.
        # This implies 'output_directory_path' was required but missing.
        # This should ideally be caught by the 'missing_vars' check earlier.
        # This log serves as a safeguard or indicates an unexpected state.
        logging.error("Output directory path is not configured and is required (not in validation mode). This should have been caught by earlier validation.")
        # To be absolutely safe, ensure this state leads to an error if not caught by missing_vars
        if 'OUTPUT_DIRECTORY_PATH' not in (name for name in missing_vars): # defensive check
             raise ValueError("Output directory path is critically missing and was not caught by initial checks.")


    # Validate and parse dates from .env strings
    try:
        start_date_str = config['audit_start_date_str_from_env']
        end_date_str = config['audit_end_date_str_from_env']
        
        config['audit_start_date'] = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        config['audit_end_date'] = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
        # Clean up temporary string keys
        del config['audit_start_date_str_from_env']
        del config['audit_end_date_str_from_env']
    except KeyError:
        # This should have been caught by missing_core_vars check
        raise ValueError("AUDIT_START_DATE or AUDIT_END_DATE missing from .env processing, or not found in config after .env load.")
    except ValueError as e: # Catches parsing errors from strptime
        raise ValueError(f"Invalid date format in .env for AUDIT_START_DATE or AUDIT_END_DATE. Use YYYY-MM-DD. Error: {e}")

    # Final check on parsed dates
    if config.get('audit_start_date') and config.get('audit_end_date'):
        if config['audit_start_date'] > config['audit_end_date']:
            raise ValueError("AUDIT_START_DATE cannot be after AUDIT_END_DATE.")
    else:
        # This state implies that one or both dates are not in the config as datetime.date objects.
        raise ValueError("Audit start or end date not properly configured or parsed.")

    logging.info("Configuration loaded successfully (merged from config.yaml and .env if present).")
    return config

if __name__ == '__main__':
    # Example usage/test when run directly
    print("Running config.py directly for testing...")
    try:
        app_config = load_config()
        print("\n--- Configuration Test Results ---")
        for key, value in app_config.items():
            print(f"{key}: {value} (Type: {type(value)})")
        print("---------------------------------")
        print("Config loading test successful.")
    except (ValueError, FileNotFoundError) as e:
        print(f"Error loading configuration: {e}")
        print("Config loading test failed.")
