# Docker Setup for BunTool

This document describes how to build and run the BunTool application using Docker.

## Prerequisites

- Docker (v20.10+)
- Docker Compose (v1.29+)

## Quick Start

### Option 1: Using Docker Compose (Recommended)

```bash
# Build and start the container
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the container
docker-compose down
```

### Option 2: Using Docker Directly

```bash
# Build the image
docker build -t buntool:latest .

# Run the container
docker run -d \
  --name buntool \
  -p 7001:7001 \
  -v buntool_tempfiles:/app/tempfiles \
  -v buntool_logs:/app/logs \
  buntool:latest

# View logs
docker logs -f buntool

# Stop the container
docker stop buntool
docker rm buntool
```

## Accessing the Application

Once the container is running:

- **Bookmark Tool**: http://localhost:7001/bookmark_tool
- **PDF Numbering Tool**: http://localhost:7001/numbering_tool
- **PDF Merger Tool**: http://localhost:7001/pdf_merger

## Features Included

The Docker image includes:

- **Python 3.11**: Core runtime environment
- **PDF Tools**: pdftk, ghostscript, pdflatex for PDF manipulation
- **LaTeX**: Full texlive installation for page number generation
- **Python Packages**: All dependencies from requirements.txt
  - Flask (web framework)
  - PyPDF (PDF reading/writing)
  - pikepdf (advanced PDF bookmark manipulation)
  - pdfplumber (PDF content extraction)
  - reportlab (PDF generation)
  - python-docx (Word document manipulation)

## Volumes

The container uses two volumes:

- **buntool_tempfiles**: Stores temporary PDF files during processing
- **buntool_logs**: Stores application logs

These are created automatically by Docker and persist between container restarts.

## Environment Variables

The container sets these environment variables automatically:

- `FLASK_APP=app.py`
- `PYTHONUNBUFFERED=1`
- `FLASK_ENV=production`

## Health Check

The container includes a health check that validates the application is responding:

```bash
# Check container health
docker ps -a | grep buntool
```

Look for `(healthy)` or `(unhealthy)` status.

## Troubleshooting

### Container won't start
```bash
docker logs buntool
```

### Port 7001 already in use
Change the port mapping in docker-compose.yml:
```yaml
ports:
  - "8080:7001"  # Access at http://localhost:8080
```

### PDF operations failing
Ensure pdftk and texlive are properly installed. Rebuild the image:
```bash
docker-compose up --build
```

### Temporary files not being cleaned
The application automatically cleans temporary files. Check `/app/tempfiles` volume:
```bash
docker exec buntool ls -la /app/tempfiles
```

## Building for Production

For production deployments with optimizations:

```bash
# Build with specific tag
docker build -t buntool:v1.0 .

# Tag for registry
docker tag buntool:v1.0 your-registry.com/buntool:v1.0

# Push to registry
docker push your-registry.com/buntool:v1.0
```

## Docker Compose with Environment File

Create a `.env` file for custom configuration:

```env
FLASK_ENV=production
PYTHONUNBUFFERED=1
```

Then reference in docker-compose.yml:

```yaml
services:
  buntool:
    env_file: .env
```

## Multi-stage Build (Advanced)

For smaller images, use a multi-stage build. Edit Dockerfile:

```dockerfile
# Stage 1: Builder
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
ENV PATH=/root/.local/bin:$PATH
CMD ["python3", "app.py"]
```

## Support

For issues or questions, refer to the main README.md or check the application logs:

```bash
docker logs -f buntool
```
