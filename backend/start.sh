#!/bin/bash
# Production startup script using Gunicorn

set -e

# Load environment variables if .env exists
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Default values
PORT=${PORT:-8015}
WORKERS=${GUNICORN_WORKERS:-2}

echo "Starting MFT Agent with Gunicorn..."
echo "Port: $PORT"
echo "Workers: $WORKERS"

exec gunicorn src.main_agent:app \
    --config gunicorn.conf.py \
    --bind 0.0.0.0:$PORT \
    --workers $WORKERS \
    --worker-class uvicorn.workers.UvicornWorker \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
