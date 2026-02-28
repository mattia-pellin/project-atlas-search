# Stage 1: Build the frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Build the backend and serve everything
FROM python:3.13-slim
WORKDIR /app

# Clean python slim image
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget ca-certificates fonts-liberation && \
    rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install them
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy everything to preserve directory structure (backend, __init__.py files, etc.)
COPY . .

# Copy the built frontend static files
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Create a separate /data directory for persistent storage (DB, credentials)
# This prevents volume mounts from overwriting application code in /app
RUN mkdir -p /data
ENV DATABASE_DIR=/data
VOLUME ["/data"]

# Expose port 8000
EXPOSE 8000

# Use entrypoint script to guarantee PYTHONPATH and CWD
ENTRYPOINT ["/app/entrypoint.sh"]
