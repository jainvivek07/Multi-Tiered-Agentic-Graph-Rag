FROM python:3.11-slim

# Install supervisor and required system libraries (libpq-dev and gcc are needed for psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    supervisor \
    curl \
    libpq-dev \
    gcc \
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
RUN uv sync --frozen --no-cache --no-install-project

# Copy the full application source
COPY --chown=appuser:appuser . .

# Install the project itself now that the source code is present
RUN uv sync --frozen --no-cache

# Expose the port required by Hugging Face Spaces
EXPOSE 7860

# Start Supervisor, which manages both FastAPI and Celery
CMD ["/usr/bin/supervisord", "-c", "/app/supervisord.conf"]
