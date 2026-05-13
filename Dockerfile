# Base Image — bullseye is more stable for CV/ML than slim default
FROM python:3.9-slim-bullseye

# Optimization: Prevent .pyc files and unbuffer Python output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Prevents OpenCV from trying to open a display (headless server)
ENV OPENCV_IO_ENABLE_OPENEXR=0
ENV DISPLAY=:99

# Set the working directory
WORKDIR /app

# System Dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgstreamer1.0-0 \
    libgstreamer-plugins-base1.0-0 \
    libavcodec-extra \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn eventlet

# Copy the rest of the application
COPY . /app/

# Expose the port
EXPOSE 5000

# Production Server
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "--timeout", "120", "--bind", "0.0.0.0:5000", "app:app"]