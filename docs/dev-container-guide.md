# Dev Container Guide for COI Auditor

## Overview

A development container (dev container) is a fully configured development environment that runs inside a Docker container. This COI Auditor project includes a complete dev container setup that provides a consistent, reproducible development environment with all necessary tools, dependencies, and configurations pre-installed.

### What is a Dev Container?

Dev containers eliminate the "it works on my machine" problem by packaging your entire development environment into a container. When you open this project in VS Code with the Dev Containers extension, it automatically builds and runs a container with:

- Python 3.11 runtime environment
- All project dependencies from `pyproject.toml`
- OCR tools (Tesseract, Poppler-utils)
- System dependencies and libraries
- 20+ VS Code extensions for Python development
- Pre-configured debugging and testing setup
- Environment variables for OCR processing

## Benefits

Using the dev container for this project provides several advantages:

- **Instant Setup**: No manual installation of Python, dependencies, or OCR tools
- **Consistency**: Everyone works with identical tools and versions
- **Isolation**: Project dependencies don't conflict with your system
- **Professional Environment**: Pre-configured with best practices and tools
- **Cross-Platform**: Works identically on Windows, macOS, and Linux
- **Easy Onboarding**: New contributors can start coding immediately
- **Reproducible Builds**: Eliminates environment-related bugs

## Prerequisites

Before using the dev container, ensure you have:

1. **VS Code**: Download from [code.visualstudio.com](https://code.visualstudio.com/)
2. **Docker Desktop**: Download from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop)
3. **Dev Containers Extension**: Install from VS Code marketplace

### System Requirements

- **Windows**: Windows 10/11 with WSL2 enabled
- **macOS**: macOS 10.15 or later
- **Linux**: Any modern distribution with Docker support
- **RAM**: Minimum 8GB recommended (4GB for container + 4GB for host)
- **Storage**: At least 5GB free space for container images

## Quick Start

### First-Time Setup (5 minutes)

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd coi-auditor
   ```

2. **Open in VS Code**:
   ```bash
   code .
   ```

3. **Open in Dev Container**:
   - VS Code will detect the dev container configuration
   - Click "Reopen in Container" when prompted
   - Or use Command Palette: `Dev Containers: Reopen in Container`

4. **Wait for build** (first time only):
   - Container builds automatically (3-5 minutes)
   - Dependencies install automatically
   - VS Code extensions configure automatically

5. **Start developing**:
   - Terminal opens in container environment
   - All tools and dependencies are ready
   - Run `python -m pytest` to verify setup

### Daily Workflow

**Opening the project**:
```bash
code .
# VS Code opens → Click "Reopen in Container"
```

**Running the COI Auditor**:
```bash
python -m coi_auditor.main
```

**Running tests**:
```bash
python -m pytest
python -m pytest tests/test_pdf_extraction.py -v
```

**Installing new dependencies**:
```bash
pip install package-name
# Add to pyproject.toml for persistence
```

## Detailed Setup

### Environment Variables

The dev container includes a template environment file at `.devcontainer/.env.container`. Copy and customize it:

```bash
# Copy template to project root
cp .devcontainer/.env.container .env

# Edit with your specific values
code .env
```

**Key environment variables**:
```bash
# OCR Configuration
TESSERACT_CMD=/usr/bin/tesseract
POPPLER_PATH=/usr/bin

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=detailed

# Development
DEBUG_MODE=true
DEVELOPMENT_MODE=true
```

### Container Validation

The dev container includes an automated validation script:

```bash
# Run validation to check setup
python .devcontainer/validate-container.py

# Expected output:
# ✅ Python 3.11 available
# ✅ All dependencies installed
# ✅ OCR tools configured
# ✅ VS Code extensions loaded
# ✅ Environment variables set
```

## Using the Dev Container

### File Access and Mounting

The dev container mounts your project directory, providing seamless file access:

- **Source code**: Directly editable in VS Code
- **Output files**: Saved to your local filesystem
- **Configuration**: Persisted between container sessions
- **Git operations**: Work normally with your local repository

### Running the COI Auditor

**Basic execution**:
```bash
# Run with default configuration
python -m coi_auditor.main

# Run with specific Excel file
python -m coi_auditor.main --excel-file "Subcontractor-Payments.xlsx"

# Run with custom configuration
python -m coi_auditor.main --config config.yaml
```

**Advanced usage**:
```bash
# Enable debug logging
LOG_LEVEL=DEBUG python -m coi_auditor.main

# Process specific PDF directory
python -m coi_auditor.main --pdf-dir "path/to/pdfs"

# Generate detailed reports
python -m coi_auditor.main --verbose --output-dir "output"
```

### Testing in the Container

**Run all tests**:
```bash
python -m pytest
```

**Run specific test categories**:
```bash
# PDF processing tests
python -m pytest tests/test_pdf_extraction.py -v

# Excel handling tests
python -m pytest tests/test_excel_loading.py -v

# End-to-end validation
python -m pytest tests/test_31w_end_to_end_validation.py -v
```

**Test with coverage**:
```bash
python -m pytest --cov=src/coi_auditor --cov-report=html
```

### Debugging in the Container

The dev container is pre-configured for debugging:

1. **Set breakpoints** in VS Code
2. **Press F5** to start debugging
3. **Use integrated terminal** for interactive debugging
4. **Access debugger console** for variable inspection

**Debug configuration** (`.vscode/launch.json` is pre-configured):
```json
{
    "name": "Debug COI Auditor",
    "type": "python",
    "request": "launch",
    "module": "coi_auditor.main",
    "console": "integratedTerminal",
    "env": {
        "PYTHONPATH": "${workspaceFolder}/src"
    }
}
```

## Performance Tips

### Optimizing Container Performance

1. **Use volume mounts efficiently**:
   - Large datasets: Store outside container, mount as needed
   - Temporary files: Use container's `/tmp` directory
   - Cache directories: Persist pip cache between builds

2. **Resource allocation**:
   ```bash
   # Check container resource usage
   docker stats
   
   # Adjust Docker Desktop settings:
   # - Memory: 4-6GB for this project
   # - CPU: 2-4 cores recommended
   ```

3. **Build optimization**:
   - Container uses multi-stage builds for efficiency
   - Dependencies are cached between rebuilds
   - Only rebuild when Dockerfile or requirements change

### Development Workflow Optimization

1. **Keep container running**: Don't rebuild unnecessarily
2. **Use integrated terminal**: Faster than external terminals
3. **Leverage VS Code features**: IntelliSense, debugging, testing
4. **Batch operations**: Install multiple packages at once

## Troubleshooting

### Common Issues and Solutions

**Container won't start**:
```bash
# Check Docker is running
docker --version

# Rebuild container
Dev Containers: Rebuild Container

# Check logs
Dev Containers: Show Container Log
```

**Permission errors**:
```bash
# Fix file permissions (Linux/macOS)
sudo chown -R $USER:$USER .

# Windows: Ensure WSL2 is properly configured
wsl --set-default-version 2
```

**OCR tools not working**:
```bash
# Verify OCR installation
tesseract --version
pdftoppm -h

# Check environment variables
echo $TESSERACT_CMD
echo $POPPLER_PATH

# Reinstall if needed
sudo apt-get update && sudo apt-get install -y tesseract-ocr poppler-utils
```

**Python dependencies missing**:
```bash
# Reinstall dependencies
pip install -e .

# Check pyproject.toml
cat pyproject.toml

# Rebuild container if needed
Dev Containers: Rebuild Container
```

**VS Code extensions not loading**:
```bash
# Check devcontainer.json
cat .devcontainer/devcontainer.json

# Reload window
Developer: Reload Window

# Reinstall extensions
Extensions: Reinstall Extension
```

### Performance Issues

**Slow container startup**:
- Increase Docker Desktop memory allocation
- Close unnecessary applications
- Use SSD storage for Docker data

**Slow file operations**:
- Use bind mounts instead of volumes for development
- Exclude large directories from VS Code file watching
- Configure `.gitignore` to exclude temporary files

**Memory issues**:
```bash
# Monitor memory usage
docker stats

# Clear Python cache
find . -type d -name __pycache__ -delete

# Clean Docker system
docker system prune
```

## Advanced Configuration

### Customizing the Dev Container

**Modify container configuration** (`.devcontainer/devcontainer.json`):
```json
{
    "customizations": {
        "vscode": {
            "settings": {
                "python.defaultInterpreterPath": "/usr/local/bin/python",
                "python.linting.enabled": true
            },
            "extensions": [
                "ms-python.python",
                "ms-python.pylint"
            ]
        }
    }
}
```

**Add system packages** (`.devcontainer/Dockerfile`):
```dockerfile
# Add custom packages
RUN apt-get update && apt-get install -y \
    your-package-here \
    && rm -rf /var/lib/apt/lists/*
```

**Environment customization**:
```bash
# Add to .devcontainer/.env.container
CUSTOM_VARIABLE=value
DEVELOPMENT_FEATURE=enabled
```

### Integration with CI/CD

The dev container configuration can be used in CI/CD pipelines:

```yaml
# GitHub Actions example
- name: Setup Dev Container
  uses: devcontainers/ci@v0.3
  with:
    imageName: coi-auditor-dev
    runCmd: python -m pytest
```

### Multi-Container Setup

For complex scenarios, extend with additional services:

```yaml
# docker-compose.yml
version: '3.8'
services:
  app:
    build: .devcontainer
    volumes:
      - .:/workspace
  database:
    image: postgres:13
    environment:
      POSTGRES_DB: coi_auditor
```

## FAQ

### General Questions

**Q: Do I need to install Python on my machine?**
A: No, Python 3.11 is included in the dev container.

**Q: Can I use this on Windows?**
A: Yes, with Docker Desktop and WSL2 enabled.

**Q: How much disk space does this use?**
A: Approximately 2-3GB for the container image and dependencies.

**Q: Can I modify the container configuration?**
A: Yes, edit files in `.devcontainer/` and rebuild the container.

### Development Questions

**Q: How do I add new Python packages?**
A: Install with `pip install package-name`, then add to `pyproject.toml` for persistence.

**Q: Can I use different Python versions?**
A: Modify the base image in `.devcontainer/Dockerfile` and rebuild.

**Q: How do I access files outside the project?**
A: Mount additional directories in `devcontainer.json` mounts configuration.

**Q: Can I run multiple projects in the same container?**
A: Each project should have its own container for isolation.

### Troubleshooting Questions

**Q: Container build fails with permission errors**
A: Ensure Docker Desktop has proper permissions and WSL2 is configured correctly.

**Q: OCR processing doesn't work**
A: Verify Tesseract and Poppler are installed by running the validation script.

**Q: VS Code is slow in the container**
A: Increase Docker Desktop memory allocation and close unnecessary extensions.

**Q: How do I reset the container completely?**
A: Use "Dev Containers: Rebuild Container" or delete the container image and rebuild.

### Performance Questions

**Q: Why is the first startup slow?**
A: The container needs to build and download dependencies. Subsequent starts are much faster.

**Q: Can I speed up the build process?**
A: The Dockerfile uses multi-stage builds and caching for optimal performance.

**Q: How do I monitor resource usage?**
A: Use `docker stats` to monitor CPU, memory, and network usage.

---

## Getting Help

If you encounter issues not covered in this guide:

1. **Check the validation script**: `python .devcontainer/validate-container.py`
2. **Review container logs**: Use "Dev Containers: Show Container Log"
3. **Consult the technical documentation**: See `.devcontainer/README.md`
4. **Check the setup guide**: See `.devcontainer/SETUP_GUIDE.md`
5. **Rebuild the container**: Use "Dev Containers: Rebuild Container"

The dev container setup is designed to provide a professional, consistent development environment that eliminates setup complexity and ensures all contributors can focus on developing the COI Auditor functionality rather than managing development tools.