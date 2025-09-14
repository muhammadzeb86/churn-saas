FROM python:3.11-slim

WORKDIR /app

# Install system dependencies and Rust toolchain
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && curl https://sh.rustup.rs -sSf | sh -s -- -y

# Add Rust to PATH
ENV PATH="/root/.cargo/bin:${PATH}"

# Copy backend directory contents to /app/backend (NOT /app/backend/backend)
# When built from repo root, this creates the correct structure
COPY backend/ ./backend/

# Install backend deps
RUN pip install --no-cache-dir -r ./backend/requirements.txt && pip install --no-cache-dir email-validator boto3

# List what was copied for verification
RUN set -eux; ls -la /app; ls -la /app/backend; ls -la /app/backend/main.py || echo "main.py not found"

# Set PYTHONPATH and verify module discovery
ENV PYTHONPATH=/app
RUN python - <<'PY'
import sys, importlib.util, pathlib
print(">> sys.path:", sys.path)
print(">> exists /app/backend/main.py:", pathlib.Path("/app/backend/main.py").exists())
spec = importlib.util.find_spec("backend.main")
print(">> find_spec for backend.main:", spec.origin if spec else "NOT FOUND")
PY

# Environment variables (set by ECS task definition)
# Required: DATABASE_URL, AWS_REGION, PREDICTIONS_QUEUE_URL, S3_BUCKET
ENV ENVIRONMENT=production

# Expose and launch
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
