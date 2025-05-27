"""
Advanced task runner for the coi-auditor project.
Run tasks with: `python tasks.py <taskname>`
Requires: invoke (pip install invoke)
"""
from invoke import task
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
PKG_DIR = os.path.join(SRC_DIR, "coi_auditor") # Actual package directory
TESTS_DIR = os.path.join(PROJECT_ROOT, "tests")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")

@task
def test(ctx):
    """Run all tests in the tests/ directory."""
    # Ensure tests are discovered from the correct directory relative to project root
    ctx.run(f"python -m unittest discover -s {TESTS_DIR} -p '*_test.py'", pty=True)

@task
def lint(ctx):
    """Run pyright type checker on src/coi_auditor and tests/ directories."""
    ctx.run(f"pyright {PKG_DIR} {TESTS_DIR}", pty=True)

@task
def clean_logs(ctx):
    """Remove all log and txt files from the logs/ directory (platform-agnostic)."""
    if not os.path.exists(LOGS_DIR):
        print(f"Logs directory '{LOGS_DIR}' does not exist. Nothing to clean.")
        return
    for filename in os.listdir(LOGS_DIR):
        if filename.endswith(".log") or filename.endswith(".txt"):
            file_path = os.path.join(LOGS_DIR, filename)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    print(f"Removed log file: {file_path}")
            except Exception as e:
                print(f"Error removing file {file_path}: {e}")
    print("Log cleaning finished.")


@task
def run(ctx):
    """Run the main COI Auditor script."""
    # Assumes running from project root, src is in PYTHONPATH or package installed
    ctx.run(f"python -m {os.path.basename(SRC_DIR)}.{os.path.basename(PKG_DIR)}.main", pty=True)

@task
def dump_log(ctx):
    """Dump the audit log using the dump_log utility."""
    ctx.run(f"python -m {os.path.basename(SRC_DIR)}.{os.path.basename(PKG_DIR)}.dump_log", pty=True)

@task
def format(ctx):
    """Format code using black."""
    ctx.run(f"black {SRC_DIR} {TESTS_DIR}", pty=True)

@task
def requirements(ctx):
    """Update requirements.txt with current environment (core packages only)."""
    ctx.run('pip freeze | findstr /R /C:"openpyxl" /C:"pdfplumber" /C:"python-dotenv" > requirements.txt', pty=True)

@task
def setup_logs(ctx):
    """Create the logs/ directory if it doesn't exist."""
    if not os.path.exists(LOGS_DIR):
        os.makedirs(LOGS_DIR)
        print("Created logs/ directory.")
    else:
        print("logs/ directory already exists.")
