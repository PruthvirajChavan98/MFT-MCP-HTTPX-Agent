# Use slim Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y     git     curl     build-essential     && rm -rf /var/lib/apt/lists/*

# Install uv globally
RUN pip install uv

# Copy dependency files first for better cache usage
COPY requirements.txt uv.lock* pyproject.toml ./

# Install Python dependencies using uv into the system environment
RUN uv pip install -r requirements.txt --system

# Copy the full project
COPY . .

# Expose ports for documentation (MCP and Agent)
EXPOSE 8050
EXPOSE 8000

# Default command (can be overridden by docker-compose)
CMD ["python", "serverNew.py"]
