# Use the official Python image.
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies and gdown for Google Drive download
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git wget python3-pip \
    && pip install gdown \
    && rm -rf /var/lib/apt/lists/*

# Copy all project files
COPY . .

# Download the model file from Google Drive using gdown
RUN gdown --id 1jvOXuZoufE6665hJu41GalmBiMjq14yO -O models/model.h5

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Expose port 8080 for platform
EXPOSE 8080

# Start the app with Gunicorn
CMD exec gunicorn --bind :8080 --workers 1 --threads 8 main:app 