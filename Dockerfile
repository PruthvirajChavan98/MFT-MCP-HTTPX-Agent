# Use slim Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv globally
RUN pip install uv

# Copy dependency files first for better cache usage
COPY requirements.txt uv.lock* pyproject.toml ./

# Install Python dependencies using uv
RUN uv pip install -r requirements.txt --system

# Copy the full project
COPY . .

# Expose port if serverNew.py runs an app (like FastAPI, Flask, etc.)
EXPOSE 8050

# Command to run your server file
CMD ["uv", "run", "serverNew.py"]
