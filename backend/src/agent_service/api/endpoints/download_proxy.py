"""One-time download proxy for document delivery via MCP tools."""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.agent_service.core.config import CRM_BASE_URL, DOWNLOAD_TOKEN_REDIS_PREFIX
from src.agent_service.core.session_utils import get_redis

log = logging.getLogger(__name__)

router = APIRouter(tags=["download"])

_CRM_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)


@router.get("/download/{token}")
async def download_document(token: str) -> StreamingResponse:
    """
    Consume a one-time download token and stream the PDF from the CRM.

    The token is created by MCP document tools (download_welcome_letter,
    download_soa) and stored in Redis with a 10-minute TTL.  Each token
    is deleted atomically on first use (single-use).
    """
    redis = await get_redis()
    redis_key = f"{DOWNLOAD_TOKEN_REDIS_PREFIX}{token}"

    # Atomic get-and-delete — ensures single-use even under concurrent requests.
    pipe = redis.pipeline(transaction=True)
    pipe.get(redis_key)
    pipe.delete(redis_key)
    results = await pipe.execute()
    token_data_raw: str | None = results[0]

    if not token_data_raw:
        raise HTTPException(status_code=404, detail="Download link expired or invalid.")

    token_data: dict = json.loads(token_data_raw)
    bearer_token: str = token_data["bearer_token"]
    method: str = token_data["method"]
    path: str = token_data["path"]
    json_body: dict | None = (
        json.loads(token_data["json_body"]) if token_data.get("json_body") else None
    )
    filename: str = token_data.get("filename") or f'{token_data.get("doc_type", "document")}.pdf'
    hint: str = token_data.get("password_hint", "")

    crm_url = f"{CRM_BASE_URL}{path}" if path.startswith("/") else f"{CRM_BASE_URL}/{path}"

    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Accept": "application/pdf",
    }
    if json_body:
        headers["Content-Type"] = "application/json"

    async def _stream_pdf() -> AsyncIterator[bytes]:
        async with httpx.AsyncClient(timeout=_CRM_TIMEOUT) as client:
            async with client.stream(method, crm_url, headers=headers, json=json_body) as resp:
                if resp.status_code not in (200, 201):
                    await resp.aread()
                    log.error("CRM download failed: %s %s", resp.status_code, resp.text[:500])
                    raise HTTPException(
                        status_code=502,
                        detail="Upstream document service returned an error.",
                    )
                async for chunk in resp.aiter_bytes(chunk_size=8192):
                    yield chunk

    response_headers: dict[str, str] = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store",
    }
    if hint:
        response_headers["X-Password-Hint"] = hint

    return StreamingResponse(
        _stream_pdf(),
        media_type="application/pdf",
        headers=response_headers,
    )
