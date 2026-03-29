# Dockerfile for Calculus Animator
# Provides containerized development environment
# Note: Desktop GUI features require X11 forwarding or VNC

FROM python:3.11-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Development stage
FROM base as development
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY . .
CMD ["python", "run_tests.py", "quick"]

# Production stage (for CI/testing only - GUI won't work in container)
FROM base as production
COPY . .
CMD ["python", "run_tests.py", "quick"]

# Labels for metadata
LABEL org.opencontainers.image.title="Calculus Animator"
LABEL org.opencontainers.image.description="Interactive calculus visualization with AI tutoring"
LABEL org.opencontainers.image.source="https://github.com/Rsan0948/calculus_animator"
LABEL org.opencontainers.image.licenses="MIT"
