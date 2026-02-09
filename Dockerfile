# Use Python 3.11 slim as base image
FROM python:3.11-slim

# 1. Устанавливаем Chromium и драйвер из репозитория Debian.
# Это заменяет и google-chrome-stable, и ручное скачивание chromedriver.
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    curl \
    unzip \
    # xvfb нужен, только если ты используешь pyvirtualdisplay, 
    # для headless режима в selenium он обычно не обязателен, но оставим на всякий случай
    xvfb \ 
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV DISPLAY=:99

# Важно: указываем правильные пути для Chromium
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

# Start command
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]