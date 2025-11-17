# Use the official Python image
FROM python:3.11-slim

# Install ffmpeg and other necessary packages
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose port
EXPOSE 5000

# Start the Flask app using Gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app", "--timeout", "120"]
