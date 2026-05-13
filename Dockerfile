# ── Base Image ───────────────────────────────────────────────────
# bullseye is more stable than slim for CV/ML workloads
FROM python:3.9-slim-bullseye

# ── Python Optimizations ─────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# ── System Dependencies ──────────────────────────────────────────
# Only what opencv-python-headless + mediapipe actually need at runtime.
# NO display/X11/GStreamer needed — we use the headless OpenCV build.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# ── Python Dependencies ──────────────────────────────────────────
# Copy requirements first (Docker cache layer — only rebuilds if requirements change)
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Application Code ─────────────────────────────────────────────
COPY . /app/

# ── Port ─────────────────────────────────────────────────────────
EXPOSE 5000

# ── Production Server ────────────────────────────────────────────
# 1 eventlet worker required for Flask-SocketIO
# --timeout 120: allows time for model to load on cold start
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "--timeout", "120", "--bind", "0.0.0.0:5000", "app:app"]