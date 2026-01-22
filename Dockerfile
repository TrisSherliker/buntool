# Use official Python runtime as a parent image
FROM python:3.11-slim

# Set working directory in container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # PDF tools
    pdftk-java \
    ghostscript \
    # LaTeX for page number generation
    texlive-latex-base \
    texlive-latex-extra \
    texlive-fonts-recommended \
    # Build essentials for Python packages
    build-essential \
    libssl-dev \
    libffi-dev \
    # Other utilities
    curl \
    wget \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire application
COPY . .

# Create directories for temporary files and logs
RUN mkdir -p /app/tempfiles /app/logs

# Expose port
EXPOSE 7001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:7001/bookmark_tool || exit 1

# Set environment variables
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production

# Run the application
CMD ["python3", "app.py"]
