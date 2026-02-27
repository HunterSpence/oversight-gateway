# Dockerfile for Oversight Gateway V2
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY oversight_gateway ./oversight_gateway
COPY oversight_gateway_sdk ./oversight_gateway_sdk
COPY policies ./policies

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Create data directory
RUN mkdir -p /data

# Set environment variables
ENV DATABASE_URL=sqlite+aiosqlite:///data/oversight_gateway.db
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8001/health')"

# Run the application
CMD ["python", "-m", "uvicorn", "oversight_gateway.main:app", "--host", "0.0.0.0", "--port", "8001"]
