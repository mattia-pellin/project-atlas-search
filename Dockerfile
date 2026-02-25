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

# Install Google Chrome + Xvfb (virtual display for headed Chrome in Docker)
# Headed Chrome bypasses Cloudflare much better than headless mode
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget ca-certificates fonts-liberation xvfb && \
    wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt-get install -y /tmp/chrome.deb && \
    rm /tmp/chrome.deb && \
    rm -f /usr/bin/wget && \
    rm -rf /var/lib/apt/lists/* && \
    google-chrome-stable --version

# Copy backend requirements and install them
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Set PYTHONPATH to the current working directory so the backend package is found
ENV PYTHONPATH=/app

# Copy everything to preserve directory structure (backend, __init__.py files, etc.)
COPY . .

# Copy the built frontend static files
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Expose port 8000
EXPOSE 8000

# Run uvicorn server
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
