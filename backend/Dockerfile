FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ ./

# Create required directories
RUN mkdir -p staticfiles

# Expose port
EXPOSE 8000

# Default command
CMD ["gunicorn", "payto.wsgi", "--bind", "0.0.0.0:8000"]
