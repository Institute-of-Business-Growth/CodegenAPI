# Dockerfile

# 1. Use an official Python runtime as a parent image (choose a specific version)
FROM python:3.13-slim as builder

# 2. Set the working directory in the container
WORKDIR /app

# 3. Install build dependencies if needed (e.g., for packages with C extensions)
# RUN apt-get update && apt-get install -y --no-install-recommends gcc build-essential && rm -rf /var/lib/apt/lists/*
# Only uncomment the above if your dependencies require compilation

# 4. Copy the requirements file first to leverage Docker cache
COPY requirements.txt .

# 5. Install Python dependencies
# --no-cache-dir keeps the image size smaller
# --default-timeout=100 increases timeout for pip if needed
RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt

# --- Second Stage: Runtime Image ---
FROM python:3.13-slim

# Install git
RUN apt-get update && \
    apt-get install -y git --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy installed packages from the builder stage
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy the application code
COPY main.py .
# If you have other modules/folders, copy them too:
# COPY ./src ./src

# 6. Expose the port the app runs on
EXPOSE 8000

# 7. Define environment variables (placeholders - provide actual values at runtime)
# It's best practice to pass secrets via the runtime environment, not build args or hardcoding
ENV CODEGEN_ORG_ID=""
ENV CODEGEN_API_TOKEN=""
ENV APP_API_KEY=""
# Set PYTHONUNBUFFERED to ensure logs are sent straight to stdout/stderr
ENV PYTHONUNBUFFERED=1

# 8. Command to run the application using Uvicorn
# Use 0.0.0.0 to bind to all network interfaces inside the container
# Use --host and --port matching the EXPOSE directive
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
