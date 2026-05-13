# ── Base Image ───────────────────────────────────────────────────
FROM python:3.9-slim-bullseye

# ── Python Optimizations ─────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# ── System Dependencies ──────────────────────────────────────────
# Minimum libs required by opencv-python-headless + mediapipe at runtime.
# NO display/GStreamer/codec libs needed — headless build has no GUI.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# ── Install PyTorch CPU First ────────────────────────────────────
# MUST use --index-url (not --extra-index-url) to force the CPU-only wheel.
# --extra-index-url lets pip choose, and it picks the CUDA version from PyPI.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch==2.1.0 --index-url https://download.pytorch.org/whl/cpu

# ── Install Remaining Dependencies ───────────────────────────────
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# ── Application Code ─────────────────────────────────────────────
COPY . /app/

# ── Port ─────────────────────────────────────────────────────────
EXPOSE 5000

# ── Production Server ────────────────────────────────────────────
# 1 eventlet worker required for Flask-SocketIO
# --timeout 120: allows cold-start time for model to load on first request
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "--timeout", "120", "--bind", "0.0.0.0:5000", "app:app"]