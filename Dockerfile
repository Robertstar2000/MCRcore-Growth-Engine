# ===========================================================================
# MCRcore Growth Engine - Dockerfile
# ===========================================================================
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies (for potential native extensions)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Create directories for runtime data
RUN mkdir -p /app/logs /app/data

# Default: run the daily pipeline
ENTRYPOINT ["python", "main.py"]
CMD ["run-daily"]
