"""
Advanced task runner for the coi-auditor project.
Run tasks with: `python tasks.py <taskname>`
Requires: invoke (pip install invoke)
"""
from invoke import task
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(PROJECT_ROOT, "coi_auditor", "src")
TESTS_DIR = os.path.join(PROJECT_ROOT, "coi_auditor", "tests")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")

@task
def test(ctx):
    """Run all tests in the tests/ directory."""
    ctx.run(f"python -m unittest discover -s {TESTS_DIR}", pty=True)

@task
def lint(ctx):
    """Run pyright type checker on src/ directory."""
    ctx.run(f"pyright {SRC_DIR}", pty=True)

@task
def clean_logs(ctx):
    """Remove all log and txt files from the logs/ directory."""
    ctx.run(f"del /Q {os.path.join(LOGS_DIR, '*.log')} {os.path.join(LOGS_DIR, '*.txt')}", pty=False, warn=True)

@task
def run(ctx):
    """Run the main COI Auditor script."""
    ctx.run("python -m coi_auditor.src.main", pty=True)

@task
def dump_log(ctx):
    """Dump the audit log using the dump_log utility."""
    ctx.run("python -m coi_auditor.src.dump_log", pty=True)

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
