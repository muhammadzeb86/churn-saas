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

# Copy entire repo into backend subdirectory
COPY . ./backend/

# Install backend deps
RUN pip install --no-cache-dir -r ./backend/requirements.txt && pip install --no-cache-dir email-validator

# List what was copied
RUN set -eux; ls -la /app; ls -la /app/backend; ls -la /app/backend/backend || true

# Show python path and confirm module is discoverable WITHOUT importing it
ENV PYTHONPATH=/app/backend
RUN python - <<'PY'
import sys, importlib.util, pathlib
print(">> sys.path:", sys.path)
print(">> exists /app/backend/backend/main.py:", pathlib.Path("/app/backend/backend/main.py").exists())
spec = importlib.util.find_spec("backend.main")
print(">> find_spec for backend.main:", spec.origin if spec else "NOT FOUND")
PY

# Expose and launch
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
