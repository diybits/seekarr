FROM python:3.11-slim

LABEL org.opencontainers.image.title="Seekarr" \
      org.opencontainers.image.description="Automated media collection management for Arr apps" \
      org.opencontainers.image.url="https://github.com/diybits/seekarr" \
      org.opencontainers.image.source="https://github.com/diybits/seekarr" \
      org.opencontainers.image.authors="diybits" \
      org.opencontainers.image.licenses="GPL-3.0"

WORKDIR /app

# Install system dependencies including net-tools for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# Install required packages from the root requirements file
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Build arg — injected by docker-release.yml; defaults to "dev" for local builds
ARG VERSION=dev

# Copy application code
COPY . /app/

# Stamp version into the image (overwrites any version.txt from the repo)
RUN echo "$VERSION" > /app/version.txt

# Create necessary directories
RUN mkdir -p /config/settings /config/stateful /config/user /config/logs
RUN chmod -R 755 /config

# Set environment variables
ENV PYTHONPATH=/app
# ENV APP_TYPE=sonarr # APP_TYPE is likely managed via config now, remove if not needed

# Expose port
EXPOSE 9705

# Run the main application using the new entry point
CMD ["python3", "main.py"]