FROM python:3.11-slim

# Set working directory to /app
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies and Rust toolchain
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && curl https://sh.rustup.rs -sSf | sh -s -- -y

# Add Rust to PATH
ENV PATH="/root/.cargo/bin:${PATH}"

# Copy requirements first to leverage Docker cache
COPY requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r ./backend/requirements.txt && pip install --no-cache-dir email-validator

# Copy the entire backend directory as a Python package
COPY . ./backend/

# Create __init__.py to make backend a proper Python package
RUN touch ./backend/__init__.py

# Expose the port
EXPOSE 8000

# Run the application with backend as a module
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"] 