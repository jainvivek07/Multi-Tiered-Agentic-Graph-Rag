FROM python:3.11-slim

# Install supervisor and required system libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    supervisor \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Hugging Face runs containers with user ID 1000. Create user and set permissions.
RUN useradd -m -u 1000 appuser
WORKDIR /app
RUN chown -R appuser:appuser /app

USER appuser

# Copy dependency manifests first (better layer caching)
COPY --chown=appuser:appuser pyproject.toml uv.lock ./

# Install dependencies without downloading extras
RUN uv sync --frozen --no-cache

# Copy the full application source
COPY --chown=appuser:appuser . .

# Expose the port required by Hugging Face Spaces
EXPOSE 7860

# Start Supervisor, which manages both FastAPI and Celery
CMD ["/usr/bin/supervisord", "-c", "/app/supervisord.conf"]
