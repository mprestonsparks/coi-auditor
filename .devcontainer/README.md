# COI Auditor Dev Container

This directory contains the development container configuration for the COI Auditor project, providing a consistent, reproducible development environment using VS Code Dev Containers.

## What's Included

### System Dependencies
- **Python 3.11** - Latest stable Python version
- **Poppler Utils** - PDF processing utilities (pre-configured)
- **Tesseract OCR** - Optical Character Recognition with English language pack
- **OpenCV Dependencies** - Image processing libraries
- **Build Tools** - GCC, make, and other compilation tools

### Python Environment
- All dependencies from [`pyproject.toml`](../pyproject.toml) automatically installed
- Development dependencies (black, pyright, invoke) included
- Additional dev container specific tools (see [`requirements.txt`](requirements.txt))

### VS Code Extensions
- **Python Development**: Python, Pylance, Black formatter, isort
- **Jupyter Support**: Full Jupyter notebook integration
- **Data Tools**: CSV editor, Rainbow CSV, PDF viewer
- **Git Integration**: GitLens, GitHub Pull Requests
- **Code Quality**: TODO highlight, spell checker, markdown tools

## Quick Start

### Prerequisites
- [VS Code](https://code.visualstudio.com/) installed
- [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) installed
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) running

### Opening the Project
1. Open VS Code
2. Open the project folder (`coi-auditor`)
3. When prompted, click "Reopen in Container" or use Command Palette:
   - `Ctrl+Shift+P` (Windows/Linux) or `Cmd+Shift+P` (Mac)
   - Type "Dev Containers: Reopen in Container"
   - Press Enter

### First Time Setup
The container will automatically:
1. Build the Docker image with all dependencies
2. Install the COI Auditor package in development mode
3. Configure VS Code with optimal settings
4. Set up environment variables for OCR tools

## Development Workflow

### Running the Application
```bash
# Using the installed command
coi-auditor

# Using the task runner
python tasks.py run

# With diagnostic mode
coi-auditor --diagnose "Subcontractor Name"
```

### Development Tasks
```bash
# Run tests
python tasks.py test

# Format code
python tasks.py format

# Run linter
python tasks.py lint

# Clean logs
python tasks.py clean-logs
```

### Working with Data
The container includes Jupyter Lab for data analysis:
```bash
# Start Jupyter Lab
jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root
```

## Environment Configuration

### Pre-configured Variables
The container automatically sets:
- `POPPLER_BIN_PATH=/usr/bin`
- `TESSERACT_CMD=/usr/bin/tesseract`
- `PYTHONPATH=/workspace/src`

### Project-specific Configuration
Create your `.env` file from the template:
```bash
cp .env.example .env
# Edit .env with your specific paths and settings
```

## File Structure

```
.devcontainer/
├── devcontainer.json    # VS Code dev container configuration
├── Dockerfile          # Container image definition
├── requirements.txt     # Additional dev dependencies
└── README.md           # This file
```

## Troubleshooting

### Container Build Issues
If the container fails to build:
1. Ensure Docker Desktop is running
2. Check available disk space (container needs ~2GB)
3. Try rebuilding: `Ctrl+Shift+P` → "Dev Containers: Rebuild Container"

### Python Dependencies
If packages are missing:
```bash
# Reinstall in development mode
pip install -e .[dev]

# Install additional dev container requirements
pip install -r .devcontainer/requirements.txt
```

### OCR Tools Not Working
The container pre-configures OCR tools, but if issues occur:
```bash
# Verify Tesseract installation
tesseract --version

# Verify Poppler installation
pdfinfo -v

# Check environment variables
echo $TESSERACT_CMD
echo $POPPLER_BIN_PATH
```

### VS Code Extensions
If extensions don't load properly:
1. Open Command Palette (`Ctrl+Shift+P`)
2. Run "Developer: Reload Window"
3. Or rebuild the container entirely

## Performance Optimization

### Volume Mounts
The container uses bind mounts for:
- `/workspace/output` - Persistent output files
- `/workspace/logs` - Log files

### Container Resources
For better performance, allocate sufficient resources in Docker Desktop:
- **Memory**: 4GB minimum, 8GB recommended
- **CPU**: 2+ cores recommended
- **Disk**: 10GB+ available space

## Customization

### Adding Extensions
Edit [`devcontainer.json`](devcontainer.json) and add to the `extensions` array:
```json
"customizations": {
    "vscode": {
        "extensions": [
            "your.extension.id"
        ]
    }
}
```

### Additional System Packages
Edit [`Dockerfile`](Dockerfile) and add to the `apt-get install` command:
```dockerfile
RUN apt-get update && apt-get install -y \
    your-package-name \
    && rm -rf /var/lib/apt/lists/*
```

### Python Packages
Add to [`requirements.txt`](requirements.txt) or modify [`pyproject.toml`](../pyproject.toml).

## Security Notes

- The container runs as a non-root user (`vscode`)
- System packages are installed during build time only
- No sensitive data should be included in the container image
- Use `.env` files for sensitive configuration (never commit these)

## Support

For dev container specific issues:
1. Check the [VS Code Dev Containers documentation](https://code.visualstudio.com/docs/devcontainers/containers)
2. Review Docker Desktop logs
3. Check this project's main [README.md](../README.md) for application-specific help

For COI Auditor application issues, refer to the main project documentation.