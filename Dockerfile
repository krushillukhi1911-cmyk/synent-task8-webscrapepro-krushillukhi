# Use official Python runtime as base image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV FLASK_CONFIG production
ENV FLASK_HOST 0.0.0.0
ENV FLASK_PORT 5000

# Set working directory
WORKDIR /app

# Install system dependencies (curl, build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers and system dependencies
RUN playwright install chromium --with-deps

# Copy project files
COPY . /app/

# Expose server port
EXPOSE 5000

# Run with Gunicorn WSGI server
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "run:app"]
