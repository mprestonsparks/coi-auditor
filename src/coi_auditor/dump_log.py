"""
A utility script to dump the contents of the main application log (coi_audit.log)
to a separate dump file (coi_audit_dump.txt) within the 'logs' directory.
This can be useful for creating a snapshot of the log at a specific time.
"""
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def dump_log_file():
    """Reads the main log file and writes its content to a dump file."""
    try:
        project_root = Path(__file__).resolve().parent.parent.parent
        logs_dir = project_root / 'logs'
        logs_dir.mkdir(exist_ok=True)

        log_path = logs_dir / 'coi_audit.log'
        dump_path = logs_dir / 'coi_audit_dump.txt'

        if not log_path.exists():
            logger.error(f"Log file not found: {log_path}")
            print(f"Error: Log file not found at {log_path}")
            return

        logger.info(f"Attempting to dump log from {log_path} to {dump_path}")
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f_log:
            log_content = f_log.read()

        with open(dump_path, 'w', encoding='utf-8') as f_dump:
            f_dump.write(log_content)

        logger.info(f"Full log successfully dumped to {dump_path}")
        print(f"Full log dumped to {dump_path}")

    except IOError as e:
        logger.error(f"IOError during log dump: {e}", exc_info=True)
        print(f"Error during log dump: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during log dump: {e}", exc_info=True)
        print(f"An unexpected error occurred: {e}")

if __name__ == '__main__':
    # Basic logging setup for direct script execution
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    dump_log_file()
