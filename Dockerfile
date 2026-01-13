FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV UV_PROJECT_ENVIRONMENT="/usr/local"
ENV UV_COMPILE_BYTECODE=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl build-essential ca-certificates \
  && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy ONLY lockfiles first
COPY pyproject.toml uv.lock ./

# Install deps
RUN uv sync --frozen --no-dev --no-install-project

# ✅ Install Playwright browsers here (depends only on deps layer)
RUN --mount=type=cache,target=/ms-playwright \
    --mount=type=cache,target=/var/cache/apt \
    mkdir -p /ms-playwright \
 && python -m playwright install --with-deps chromium

# Now copy your code (changes here won't redo Chromium)
COPY . .

RUN uv sync --frozen --no-dev

EXPOSE 8050
EXPOSE 8000
CMD ["python", "src/main_mcp.py"]
