# Multi-stage build for lumarr
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /build

# Copy project files
COPY pyproject.toml .
COPY src/ src/

# Build wheel
RUN pip install --no-cache-dir build && \
    python -m build --wheel

# Final stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash lumarr

# Set working directory
WORKDIR /app

# Copy built wheel from builder
COPY --from=builder /build/dist/*.whl /tmp/

# Install the application
RUN pip install --no-cache-dir /tmp/*.whl && \
    rm -rf /tmp/*.whl

# Create directories for config and data with proper permissions
RUN mkdir -p /config /data && \
    chown -R lumarr:lumarr /config /data

# Switch to non-root user
USER lumarr

# Set volume mount points
VOLUME ["/config", "/data"]

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    CONFIG_PATH=/config/config.yaml \
    DB_PATH=/data/lumarr.db

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import lumarr" || exit 1

# Entry point
ENTRYPOINT ["lumarr"]

# Default command (show help)
CMD ["--help"]
