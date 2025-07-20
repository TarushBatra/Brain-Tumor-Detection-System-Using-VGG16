# Use the official Python image.
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy your app code
COPY . .

# Expose port 8080 for platform
EXPOSE 8080

# Start the app with Gunicorn
CMD exec gunicorn --bind :8080 --workers 1 --threads 8 main:app 