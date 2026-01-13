FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# 1. Install system dependencies (no changes)
RUN apt-get update && apt-get install -y git curl build-essential && rm -rf /var/lib/apt/lists/*

# 2. Install uv (using the official image is often cleaner/faster than pip)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 3. Configure uv to install into the system Python
#    This replaces the need for --system flags later
ENV UV_PROJECT_ENVIRONMENT="/usr/local"
#    Enable bytecode compilation for faster startup
ENV UV_COMPILE_BYTECODE=1

# 4. Copy dependency files first (for Docker caching)
COPY pyproject.toml uv.lock ./

# 5. Install dependencies from the lockfile
#    --frozen: strictly use uv.lock (fails if out of sync)
#    --no-dev: exclude development dependencies (optional, recommended for prod)
#    --no-install-project: only install dependencies, not the app itself yet
RUN uv sync --frozen --no-dev --no-install-project

# 6. Copy the rest of the application
COPY . .

# 7. Install the project itself (if your code is a package)
#    If it's just scripts, this step might be optional, but good practice
RUN uv sync --frozen --no-dev

EXPOSE 8050
EXPOSE 8000

# Default command
CMD ["python", "src/main_mcp.py"]