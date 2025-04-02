# Use the slim variant for smaller image size
FROM python:3.12.2-slim

# Set working directory
WORKDIR /app

# Copy only requirements file first to leverage Docker cache
COPY requirements.txt .

# Install dependencies in a single RUN command to reduce layers
# and clean up cache to reduce image size
RUN pip install --no-cache-dir -r requirements.txt && \
    apt-get update && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy only the necessary files
COPY expense_manager.py group.py main.py ./
COPY templates/ ./templates/
COPY .env ./

# Expose any necessary ports (adjust as needed)
EXPOSE 80

# Run gunicorn directly instead of using a start script
CMD ["gunicorn", "-w", "1", "-k", "eventlet", "-b", "0.0.0.0:80", "--timeout", "300", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "debug", "main:app"]