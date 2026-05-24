# syntax=docker/dockerfile:1.4

# Stage 1: The Builder
FROM python:3.11-alpine AS builder

# Install build-time dependencies for Nuitka (C compiler etc.)
RUN apk add --no-cache build-base

WORKDIR /app

# Copy dependency files first to leverage Docker layer caching
COPY pyproject.toml README.md ./

# Upgrade pip and install build tool with cache mount
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install build

# Copy project source
COPY buntool ./buntool
COPY licenses ./licenses

# Build the Nuitka-compiled wheel
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m build --wheel

# Stage 2: The Runner
FROM python:3.11-alpine

# Install runtime system dependencies
RUN apk add --no-cache qpdf

# Create non-root user and group
RUN addgroup -S buntool_group && adduser -S buntool_user -G buntool_group

WORKDIR /app

# Create directories for logs, temp files, and bundles
RUN mkdir -p tempfiles logs bundles && \
    chown -R buntool_user:buntool_group /app

# Copy the compiled wheel from builder stage
COPY --from=builder /app/dist/*.whl .

# Install the wheel with pip cache mount
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install *.whl && rm *.whl

# Switch to non-root user
USER buntool_user

# Expose application port
EXPOSE 7001

# Define command to run the application
CMD ["buntool"]
