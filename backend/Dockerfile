# ---- base ----
FROM python:3.11-slim AS base
WORKDIR /app

# Install system dependencies and Rust toolchain
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && curl https://sh.rustup.rs -sSf | sh -s -- -y

# Add Rust to PATH
ENV PATH="/root/.cargo/bin:${PATH}"

# Copy only backend into image
COPY backend/ /app/

# Install backend deps
RUN pip install --no-cache-dir -r /app/requirements.txt && pip install --no-cache-dir email-validator

# Ensure Python can import "backend.*"
ENV PYTHONPATH=/app

# Build-time sanity: prove we can import backend.main
RUN python - <<'PY'
import importlib, sys, pathlib
print("PYTHONPATH:", sys.path)
m = importlib.import_module("backend.main")
print("Imported OK:", m.__file__)
PY

# Expose and launch
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
