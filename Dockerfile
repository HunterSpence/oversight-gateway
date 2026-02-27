# Multi-stage Docker build for Oversight Gateway

FROM python:3.11-slim as builder

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM python:3.11-slim

WORKDIR /app

# Copy dependencies from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY oversight_gateway/ ./oversight_gateway/
COPY oversight_gateway_sdk/ ./oversight_gateway_sdk/

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Expose port
EXPOSE 8001

# Create volume mount point for SQLite database
VOLUME ["/app/data"]

# Set environment variable for database location
ENV DATABASE_URL=sqlite:///./data/oversight_gateway.db

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8001/health').raise_for_status()"

# Run the application
CMD ["python", "-m", "uvicorn", "oversight_gateway.main:app", "--host", "0.0.0.0", "--port", "8001"]
