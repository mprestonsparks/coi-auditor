# COI Auditor Dev Container Setup Guide

This guide provides step-by-step instructions for setting up and using the COI Auditor development container.

## 📋 Prerequisites

Before you begin, ensure you have the following installed:

1. **VS Code** - [Download here](https://code.visualstudio.com/)
2. **Dev Containers Extension** - Install from VS Code marketplace
3. **Docker Desktop** - [Download here](https://www.docker.com/products/docker-desktop/)

### System Requirements
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 10GB+ free space
- **CPU**: 2+ cores recommended

## 🚀 Quick Setup

### Step 1: Clone and Open Project
```bash
git clone <repository-url>
cd coi-auditor
code .
```

### Step 2: Open in Container
When VS Code opens, you'll see a notification:
- Click **"Reopen in Container"**

Or manually:
- Press `Ctrl+Shift+P` (Windows/Linux) or `Cmd+Shift+P` (Mac)
- Type "Dev Containers: Reopen in Container"
- Press Enter

### Step 3: Wait for Setup
The container will automatically:
1. Build the Docker image (~5-10 minutes first time)
2. Install all Python dependencies
3. Run validation checks
4. Configure VS Code extensions

### Step 4: Configure Environment
```bash
# Copy environment template
cp .env.example .env

# Edit with your specific settings
nano .env
```

Required settings in `.env`:
```bash
AUDIT_START_DATE=2023-01-01
AUDIT_END_DATE=2023-12-31
EXCEL_FILE_PATH=path/to/your/subcontractors.xlsx
PDF_DIRECTORY_PATH=path/to/your/pdf/directory
OUTPUT_DIRECTORY_PATH=output
EXCEL_HEADER_ROW=1
GL_FROM_COL=D
GL_TO_COL=F
WC_FROM_COL=G
WC_TO_COL=I
```

## 🔧 Container Features

### Pre-installed System Tools
- ✅ **Python 3.11** with all project dependencies
- ✅ **Poppler Utils** for PDF processing
- ✅ **Tesseract OCR** with English language pack
- ✅ **OpenCV** and image processing libraries
- ✅ **Git** and development tools

### VS Code Extensions
- 🐍 **Python Development**: Python, Pylance, Black, isort
- 📊 **Data Analysis**: Jupyter Lab, CSV editor, PDF viewer
- 🔍 **Code Quality**: Linting, formatting, spell checking
- 📝 **Documentation**: Markdown tools, YAML support
- 🔗 **Git Integration**: GitLens, GitHub integration

### Environment Variables
The container automatically sets:
```bash
POPPLER_BIN_PATH=/usr/bin
TESSERACT_CMD=/usr/bin/tesseract
PYTHONPATH=/workspace/src
```

## 🎯 Development Workflow

### Running the Application
```bash
# Main application
coi-auditor

# With diagnostic mode
coi-auditor --diagnose "Subcontractor Name"

# Using task runner
python tasks.py run
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

### Data Analysis
```bash
# Start Jupyter Lab
jupyter lab --ip=0.0.0.0 --port=8888 --no-browser

# Access at: http://localhost:8888
```

## 🔍 Validation and Troubleshooting

### Run Container Validation
```bash
python .devcontainer/validate-container.py
```

This checks:
- ✅ Python version and packages
- ✅ System tools (Tesseract, Poppler)
- ✅ Environment variables
- ✅ Project structure
- ✅ COI Auditor installation

### Common Issues

#### Container Build Fails
```bash
# Check Docker Desktop is running
docker --version

# Rebuild container
Ctrl+Shift+P → "Dev Containers: Rebuild Container"
```

#### Missing Dependencies
```bash
# Reinstall packages
pip install -e .[dev]
pip install -r .devcontainer/requirements.txt
```

#### OCR Tools Not Working
```bash
# Verify installations
tesseract --version
pdfinfo -v

# Check environment variables
echo $TESSERACT_CMD
echo $POPPLER_BIN_PATH
```

#### VS Code Extensions Missing
```bash
# Reload window
Ctrl+Shift+P → "Developer: Reload Window"

# Or rebuild container
Ctrl+Shift+P → "Dev Containers: Rebuild Container"
```

## 📁 Container File Structure

```
/workspace/                 # Project root
├── src/coi_auditor/       # Source code
├── tests/                 # Test files
├── output/                # Generated reports (persistent)
├── logs/                  # Log files (persistent)
├── .devcontainer/         # Container configuration
├── .env                   # Your environment settings
├── config.yaml            # Application configuration
└── pyproject.toml         # Python dependencies
```

## 🔒 Security Notes

- Container runs as non-root user (`vscode`)
- No sensitive data in container image
- Use `.env` files for configuration (never commit these)
- System packages installed at build time only

## 🎨 Customization

### Adding VS Code Extensions
Edit `.devcontainer/devcontainer.json`:
```json
"extensions": [
    "existing.extension",
    "your.new.extension"
]
```

### Adding System Packages
Edit `.devcontainer/Dockerfile`:
```dockerfile
RUN apt-get update && apt-get install -y \
    your-package-name \
    && rm -rf /var/lib/apt/lists/*
```

### Adding Python Packages
Add to `.devcontainer/requirements.txt` or `pyproject.toml`

## 📚 Additional Resources

- [VS Code Dev Containers Documentation](https://code.visualstudio.com/docs/devcontainers/containers)
- [Docker Desktop Documentation](https://docs.docker.com/desktop/)
- [COI Auditor Main Documentation](../README.md)

## 🆘 Getting Help

1. **Container Issues**: Check Docker Desktop logs
2. **Application Issues**: See main [README.md](../README.md)
3. **VS Code Issues**: Check Output panel → Dev Containers

---

**Happy Coding! 🎉**

The dev container provides a complete, consistent development environment for the COI Auditor project. All dependencies are pre-configured and ready to use.