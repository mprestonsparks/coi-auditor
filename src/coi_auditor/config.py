"""Loads configuration from the .env file."""

import os
from dotenv import load_dotenv
from datetime import datetime
import logging
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from rich.logging import RichHandler
from rich.console import Console

logger = logging.getLogger(__name__)

def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
    """
    Sets up logging using RichHandler for console and optionally a FileHandler.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Basic formatter for file logs, RichHandler handles its own console formatting
    file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Configure root logger
    # Wipe any handlers another library may have installed
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[],
        force=True              # <-- KEY: guarantees a clean slate (Py ≥ 3.8)
    )
    
    root_logger = logging.getLogger() # Get the root logger
    # Ensure our package loggers inherit the new root settings
    logging.getLogger("coi_auditor").setLevel(logging.DEBUG)
    
    # Add RichHandler for console output
    console = Console(stderr=True) # Log to stderr by default like standard logging
    rich_handler = RichHandler(
        level=log_level,
        console=console,
        rich_tracebacks=True,
        markup=True, # Enable Rich markup in log messages
        tracebacks_show_locals=True,
        tracebacks_width=console.width # Use full console width for tracebacks
    )
    root_logger.addHandler(rich_handler)
    
    if log_file:
        log_file_path = Path(log_file)
        try:
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
            file_handler.setLevel(log_level)
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
            logger.info(f"File logging enabled: [cyan]{log_file_path}[/cyan]")
        except Exception as e:
            logger.error(f"[bold red]Failed to set up file logging to {log_file_path}: {e}[/bold red]")

    # ---- DEBUG-OCR visibility helper ----
    ocr_log = logging.getLogger("coi_auditor.pdf_parser")
    ocr_log.setLevel(logging.DEBUG)        # CRITICAL will propagate; DEBUG remains for fine-grained tests


    logger.info(f"Logging setup complete. Console level: [yellow]{level.upper()}[/yellow].")


def load_config() -> Dict[str, Any]:
    """Load configuration from config.yaml and .env file."""
    is_validation_mode = os.getenv('COI_VALIDATION_MODE') == '1'
    if is_validation_mode:
        logger.info("COI_VALIDATION_MODE is active. Path requirements (EXCEL_FILE_PATH, PDF_DIRECTORY_PATH, OUTPUT_DIRECTORY_PATH) will be relaxed.")

    # Determine the project root directory.
    # config.py is located at project_root/src/coi_auditor/config.py
    project_root = Path(__file__).resolve().parent.parent.parent
    
    config: Dict[str, Any] = {}

    # 1. Load from config.yaml (base configuration)
    yaml_config_path = project_root / 'config.yaml'
    if yaml_config_path.exists():
        try:
            with open(yaml_config_path, 'r', encoding='utf-8') as f:
                yaml_data = yaml.safe_load(f)
                if yaml_data:
                    config.update(yaml_data)
                    logger.info(f"Loaded base configuration from: [cyan]{yaml_config_path}[/cyan]")
                else:
                    logger.warning(f"[yellow]config.yaml at {yaml_config_path} is empty. No YAML configuration loaded.[/yellow]")
        except yaml.YAMLError as e:
            logger.error(f"[bold red]Error parsing YAML from {yaml_config_path}: {e}[/bold red]")
        except Exception as e:
            logger.error(f"[bold red]Could not read or process {yaml_config_path}: {e}[/bold red]")
    else:
        logger.warning(
            f"[yellow]config.yaml not found at {yaml_config_path}. "
            "Proceeding without YAML-based configuration. "
            "New features requiring config.yaml may not function correctly or use defaults.[/yellow]"
        )

    # 2. Load from .env file (can override YAML or add .env-specific settings)
    dotenv_path_project_root = project_root / '.env'
    # os.getcwd() returns a string, so convert to Path for consistency
    dotenv_path_cwd = Path(os.getcwd()) / '.env'

    actual_dotenv_path_str: Optional[str] = None # For load_dotenv which expects str or None
    
    if dotenv_path_project_root.exists():
        actual_dotenv_path_str = str(dotenv_path_project_root)
    elif dotenv_path_cwd.exists():
        actual_dotenv_path_str = str(dotenv_path_cwd)
        logger.info(f".env not found in project root ([cyan]{dotenv_path_project_root}[/cyan]), using .env from current working directory: [cyan]{dotenv_path_cwd}[/cyan]")
    
    if actual_dotenv_path_str:
        load_dotenv(dotenv_path=actual_dotenv_path_str, override=True)
        logger.info(f"Loaded .env variables from: [cyan]{actual_dotenv_path_str}[/cyan]. These can override config.yaml settings.")
    else:
        logger.warning(
            f"[yellow].env file not found in project root ([cyan]{dotenv_path_project_root}[/cyan]) or CWD ([cyan]{dotenv_path_cwd}[/cyan]). "
            "Relying on environment variables already set in the shell, or values from config.yaml.[/yellow]"
        )

    # Populate/override config from environment variables for specific, known keys
    env_vars_to_map = {
        'excel_file_path': 'EXCEL_FILE_PATH',
        'pdf_directory_path': 'PDF_DIRECTORY_PATH',
        'output_directory_path': 'OUTPUT_DIRECTORY_PATH',
        'excel_header_row': 'EXCEL_HEADER_ROW',
        'gl_from_col': 'GL_FROM_COL',
        'gl_to_col': 'GL_TO_COL',
        'wc_from_col': 'WC_FROM_COL',
        'wc_to_col': 'WC_TO_COL',
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
    optional_if_validation_mode_keys = [
        'EXCEL_FILE_PATH',
        'PDF_DIRECTORY_PATH',
        'OUTPUT_DIRECTORY_PATH',
    ]
    # Excel configuration keys that are always required
    always_required_keys = [
        'AUDIT_START_DATE',
        'AUDIT_END_DATE',
        'EXCEL_HEADER_ROW',
        'GL_FROM_COL',
        'GL_TO_COL',
        'WC_FROM_COL',
        'WC_TO_COL',
    ]

    missing_vars = []

    # Check path variables (optional in validation mode)
    for env_name in optional_if_validation_mode_keys:
        env_value = os.getenv(env_name)
        if env_value is None or env_value.strip() == '':
            if not is_validation_mode: # Only required if not in validation mode
                missing_vars.append(env_name)
            else:
                logger.info(f"Validation mode: Optional var '[yellow]{env_name}[/yellow]' not found or not set, proceeding.")
    
    # Check always required variables by checking the actual environment variables
    for env_name in always_required_keys:
        env_value = os.getenv(env_name)
        if env_value is None or env_value.strip() == '':
            missing_vars.append(env_name)

    if missing_vars:
        raise ValueError(f"Missing required environment variable(s) or .env entries: {', '.join(missing_vars)}")

    # Convert paths to absolute paths
    for path_key in ['excel_file_path', 'pdf_directory_path', 'output_directory_path']:
        if path_key in config and config[path_key] and isinstance(config[path_key], str): # Ensure key exists, is not None, and is a string
            # Convert to Path object then resolve to absolute path
            config[path_key] = str(Path(config[path_key]).resolve())


    # Ensure output directory exists if it's configured
    output_dir_str = config.get('output_directory_path') # Will be None if not set
    
    if output_dir_str and isinstance(output_dir_str, str): # Only proceed if output_dir_str has a value and is a string
        output_dir_path = Path(output_dir_str)
        if not output_dir_path.exists():
            try:
                output_dir_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created output directory: [cyan]{output_dir_path}[/cyan]")
            except OSError as e:
                if not is_validation_mode:
                    raise ValueError(f"Could not create configured output directory: {output_dir_path}. Error: {e}")
                else:
                    logger.warning(f"[yellow]Validation mode: Could not create (optionally provided) output directory '{output_dir_path}'. Error: {e}[/yellow]")
        elif not output_dir_path.is_dir():
            if not is_validation_mode:
                raise ValueError(f"Configured output directory path exists but is not a directory: {output_dir_path}")
            else:
                logger.warning(f"[yellow]Validation mode: (Optionally provided) output directory path '{output_dir_path}' exists but is not a directory.[/yellow]")
    elif not is_validation_mode and ('output_directory_path' not in config or not config['output_directory_path']):
        # This case means output_dir_str is None/empty AND we are NOT in validation mode.
        logger.error("[bold red]Output directory path is not configured and is required (not in validation mode). This should have been caught by earlier validation.[/bold red]")
        # To be absolutely safe, ensure this state leads to an error if not caught by missing_vars
        if 'OUTPUT_DIRECTORY_PATH' not in (name for name in missing_vars): # defensive check
             raise ValueError("Output directory path is critically missing and was not caught by initial checks.")


    # Validate and parse dates from .env strings
    # Only proceed if we have the date strings (missing vars check above would have caught missing dates)
    if 'audit_start_date_str_from_env' in config and 'audit_end_date_str_from_env' in config:
        try:
            start_date_str = config['audit_start_date_str_from_env']
            end_date_str = config['audit_end_date_str_from_env']
            
            config['audit_start_date'] = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            config['audit_end_date'] = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
            # Clean up temporary string keys
            del config['audit_start_date_str_from_env']
            del config['audit_end_date_str_from_env']
        except ValueError as e: # Catches parsing errors from strptime
            raise ValueError(f"Invalid date format in .env for AUDIT_START_DATE or AUDIT_END_DATE. Use YYYY-MM-DD format. Error: {e}")
    else:
        # This should have been caught by missing_vars check above
        raise ValueError("AUDIT_START_DATE or AUDIT_END_DATE missing from environment variables.")

    # Final check on parsed dates
    if config.get('audit_start_date') and config.get('audit_end_date'):
        if config['audit_start_date'] > config['audit_end_date']:
            raise ValueError("AUDIT_START_DATE cannot be after AUDIT_END_DATE.")
    else:
        # This state implies that one or both dates are not in the config as datetime.date objects.
        raise ValueError("Audit start or end date not properly configured or parsed.")

    logger.info("Configuration loaded successfully (merged from config.yaml and .env if present).")
    return config

if __name__ == '__main__':
    # Example usage/test when run directly
    print("Running config.py directly for testing...")
    setup_logging() # Setup logging for the test run
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
