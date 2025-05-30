# COI Auditor Development Container
FROM python:3.11-slim

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies for OCR, PDF processing, and development tools
RUN apt-get update && apt-get install -y \
    # Basic development tools
    git \
    curl \
    wget \
    build-essential \
    pkg-config \
    # PDF processing dependencies (Poppler)
    poppler-utils \
    # Tesseract OCR and language packs
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    # Image processing libraries for OpenCV and PIL
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgeos-dev \
    # Additional image processing dependencies
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libwebp-dev \
    libopenjp2-7-dev \
    # For PaddleOCR dependencies
    libgfortran5 \
    libopenblas-dev \
    # System utilities
    vim \
    nano \
    htop \
    tree \
    # Clean up
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set up Poppler environment variable for the container
ENV POPPLER_BIN_PATH=/usr/bin

# Set up Tesseract environment variable for the container
ENV TESSERACT_CMD=/usr/bin/tesseract

# Create a non-root user for development
RUN useradd -m -s /bin/bash vscode \
    && usermod -aG sudo vscode \
    && echo "vscode ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Set working directory
WORKDIR /workspace

# Copy project files for dependency installation
COPY pyproject.toml ./
COPY config.yaml ./
COPY .env.example ./

# Upgrade pip and install Python dependencies
RUN pip install --upgrade pip setuptools wheel

# Install the project in development mode with all dependencies
# This will install both core and dev dependencies
RUN pip install -e .[dev]

# Create necessary directories
RUN mkdir -p /workspace/output \
    && mkdir -p /workspace/logs \
    && chown -R vscode:vscode /workspace

# Switch to non-root user
USER vscode

# Set up shell environment for the user
RUN echo 'alias ll="ls -la"' >> ~/.bashrc \
    && echo 'alias la="ls -la"' >> ~/.bashrc \
    && echo 'export PATH="/home/vscode/.local/bin:$PATH"' >> ~/.bashrc

# Expose any ports if needed (none required for this project currently)
# EXPOSE 8000

# Set the default command
CMD ["/bin/bash"]