# Base Image
FROM python:3.9-slim

# Optimization: Prevent .pyc files and unbuffer Python output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# System Dependencies: Install critical Linux libraries for OpenCV and MediaPipe
# System Dependencies: Install modern Linux libraries for OpenCV and MediaPipe
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install gunicorn eventlet

# Copy the rest of the application
COPY . /app/

# Expose the port the app runs on
EXPOSE 5000

# Production Server Configuration: Run Gunicorn with Eventlet worker class
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "--timeout", "120", "app:app", "--bind", "0.0.0.0:5000"]

