FROM python:3.10-slim

# Install ffmpeg
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Create required directories
RUN mkdir -p temp_downloads results

# Expose port
EXPOSE 10000

# Start with gunicorn
CMD ["gunicorn", "webapp.app:app", "--bind", "0.0.0.0:10000", "--workers", "1", "--threads", "2", "--timeout", "120"]
