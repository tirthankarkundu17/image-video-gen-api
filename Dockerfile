# Use official lightweight Python image
FROM python:3.13-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

# Install uv for fast dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency specifications
COPY pyproject.toml .python-version ./

# Install dependencies using uv into system environment
RUN uv pip install --system -r pyproject.toml

# Copy application source code
COPY app/ app/
COPY main.py .

# Expose container port (Cloud Run defaults to 8080)
EXPOSE 8080

# Run FastAPI with Uvicorn, dynamically binding to $PORT injected by Cloud Run
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
