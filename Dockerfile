FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies for building packages
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt requirements-fallback.txt ./

# Try main requirements first, fallback if needed
RUN pip install --upgrade pip && \
    (pip install -r requirements.txt || pip install -r requirements-fallback.txt)

# Copy application code
COPY src/ ./src/
COPY templates/ ./templates/
COPY app.py .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "app.py"]