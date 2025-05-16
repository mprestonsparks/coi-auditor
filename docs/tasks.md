# Project Task Automation with tasks.py

This project uses a powerful `tasks.py` script (powered by [Invoke](https://www.pyinvoke.org/)) for advanced automation of common development and maintenance tasks.

## Getting Started

1. **Install Invoke:**
   ```sh
   pip install invoke
   ```
2. **Run a Task:**
   ```sh
   python tasks.py <taskname>
   ```
   For example, to run all tests:
   ```sh
   python tasks.py test
   ```

## Available Tasks

- **test**: Run all tests in `coi_auditor/tests/`.
- **lint**: Run static type checking on `src/` using `pyright`.
- **clean_logs**: Remove all `.log` and `.txt` files from the `logs/` directory.
- **run**: Run the main COI Auditor script (`python -m coi_auditor.src.main`).
- **dump_log**: Run the log dump utility (`python -m coi_auditor.src.dump_log`).
- **format**: Format all code using `black`.
- **requirements**: Update `requirements.txt` with only the project's core dependencies.
- **setup_logs**: Create the `logs/` directory if it doesn't exist.

## Why Use tasks.py?
- **Consistency:** All developers use the same commands for common tasks.
- **Convenience:** No need to remember long shell commands.
- **Cross-platform:** Python-based, so works on Windows, Mac, and Linux.
- **Extensible:** Add new tasks as your workflow grows.

## Customizing
You can add your own tasks to `tasks.py` using the `@task` decorator. See the [Invoke documentation](https://docs.pyinvoke.org/en/stable/) for more details.

---

For any questions or to suggest improvements, please open an issue or pull request!
