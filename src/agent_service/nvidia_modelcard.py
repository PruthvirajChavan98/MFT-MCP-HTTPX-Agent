# ===== nvidia_modelcard.py =====
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup

_DISABLED_ATTRS = {
    "disabled",
    "aria-disabled",
    "data-disabled",
    "data-state",
}

DEFAULT_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://build.nvidia.com/",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

WRENCH_PATTERNS = [
    re.compile(r"wrench\.svg", re.IGNORECASE),
    re.compile(r'data-icon-name\s*=\s*["\']wrench["\']', re.IGNORECASE),
    re.compile(r'href\s*=\s*["\']#wrench_\d+["\']', re.IGNORECASE),
    re.compile(r'id\s*=\s*["\']wrench_\d+["\']', re.IGNORECASE),
]

@dataclass
class NvidiaBuildPageResult:
    url: str
    status_code: int
    html_len: int
    fetched_at: float

class NvidiaBuildPageScraper:
    """
    Scrapes NVIDIA Build pages WITHOUT JS.
    For tool-calling inference, we scrape the base page:
      https://build.nvidia.com/<vendor>/<model>
    """
    def __init__(
        self,
        *,
        http2: bool = True,
        timeout_s: float = 20.0,
        retries: int = 3,
        backoff_s: float = 0.8,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.http2 = http2
        self.timeout_s = timeout_s
        self.retries = max(1, int(retries))
        self.backoff_s = float(backoff_s)
        self.headers = dict(DEFAULT_HEADERS)
        if headers:
            self.headers.update(headers)

    @staticmethod
    def model_id_to_base_url(model_id: str) -> str:
        mid = (model_id or "").strip().strip("/")
        return f"https://build.nvidia.com/{mid}"

    async def fetch_html(self, url: str) -> Tuple[int, str]:
        last_err: Optional[Exception] = None
        timeout = httpx.Timeout(self.timeout_s, connect=min(10.0, self.timeout_s))

        async with httpx.AsyncClient(http2=self.http2, follow_redirects=True, timeout=timeout) as client:
            for attempt in range(1, self.retries + 1):
                try:
                    r = await client.get(url, headers=self.headers)
                    return int(r.status_code), (r.text or "")
                except Exception as e:
                    last_err = e
                    await self._sleep_backoff(attempt)

        raise RuntimeError(f"Failed to fetch {url}: {last_err}")

    async def _sleep_backoff(self, attempt: int) -> None:
        import asyncio
        delay = min(self.backoff_s * (2 ** (attempt - 1)), 6.0)
        await asyncio.sleep(delay)

    async def scrape_model_page(self, model_id: str) -> Tuple[NvidiaBuildPageResult, str]:
        url = self.model_id_to_base_url(model_id)
        status, html = await self.fetch_html(url)
        res = NvidiaBuildPageResult(
            url=url,
            status_code=status,
            html_len=len(html or ""),
            fetched_at=time.time(),
        )
        return res, (html or "")

def infer_tool_support_from_wrench(html: str) -> Tuple[Optional[bool], List[str]]:
    """
    Your rule:
      If wrench icon element exists => tool calling model.
    Returns (True/None) with evidence snippets.
    """
    html = html or ""
    evidence: List[str] = []

    for pat in WRENCH_PATTERNS:
        m = pat.search(html)
        if m:
            evidence.append(f"wrench:{pat.pattern} => {m.group(0)}")
            return True, evidence[:10]

    return None, evidence

def infer_tool_support_from_tools_button(html: str) -> Tuple[Optional[bool], List[str]]:
    soup = BeautifulSoup(html or "", "lxml")

    for btn in soup.find_all("button"):
        txt = (btn.get_text(" ", strip=True) or "").strip()
        if txt != "Tools":
            continue

        attrs = {k: (v if v is not None else True) for k, v in (btn.attrs or {}).items()}
        aria = str(attrs.get("aria-disabled", "")).strip().lower()
        data_state = str(attrs.get("data-state", "")).strip().lower()

        is_disabled = (
            ("disabled" in attrs) or
            ("data-disabled" in attrs) or
            (aria == "true") or
            (data_state == "disabled")
        )

        snippet = str(btn)[:500]
        ev = [f"btn={snippet}", f"attrs={attrs}"]

        return (False if is_disabled else True), ev

    return None, []
