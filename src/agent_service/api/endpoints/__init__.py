"""
API Endpoints Package
Groups related endpoints into logical modules.
"""
from fastapi import APIRouter

# Create a main router for agent endpoints
agent_router = APIRouter(prefix="/agent", tags=["agent"])
