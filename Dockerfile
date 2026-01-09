FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

RUN apt-get update && apt-get install -y git curl build-essential && rm -rf /var/lib/apt/lists/*
RUN pip install uv

COPY requirements.txt uv.lock* pyproject.toml ./
RUN uv pip install -r requirements.txt --system

COPY . .

EXPOSE 8050
EXPOSE 8000

# Default command (overridden by compose)
CMD ["python", "src/main_mcp.py"]
