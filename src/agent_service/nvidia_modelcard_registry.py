from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

from redis.asyncio import Redis

log = logging.getLogger("nvidia_modelcard_registry")

try:
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout  # type: ignore
except Exception:  # pragma: no cover
    async_playwright = None  # type: ignore
    PWTimeout = Exception  # type: ignore


class NvidiaModelcardRegistry:
    """
    Purpose:
      - detect tool-calling support per NVIDIA Build model page
      - cache it in Redis
      - refresh on:
          - NEW models (scrape immediately)
          - EXISTING models (revalidate weekly)
      - cap scrapes per refresh to avoid hammering Playwright/NVIDIA

    Detection (JS-rendered page):
      tool_supported = Tools button exists AND not disabled AND wrench icon exists
      (this matches your Playwright verification exactly)
    """

    KNOWN_SET_KEY = "agent:nvidia:modelcards:known"
    CARD_KEY_PREFIX = "agent:nvidia:modelcard:"  # + <model_id_lower>

    # If you want forced overrides, keep them here.
    # (Not required once Playwright works, but fine as safety.)
    HARDCODED_TOOL_SUPPORT: Dict[str, bool] = {
        "deepseek-ai/deepseek-r1": False,
        "deepseek-ai/deepseek-r1-0528": True,
        "openai/gpt-oss-120b": True,
        "openai/gpt-oss-20b": True,
    }

    DEFAULT_UA = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(
        self,
        redis: Redis,
        *,
        validate_interval_seconds: int = 7 * 24 * 3600,   # weekly validation
        max_scrapes_per_run: int = 6,
        concurrency: int = 3,
        min_rescrape_seconds: int = 24 * 3600,            # don't rescrape same model within 24h
        nav_timeout_ms: int = 60_000,
        networkidle_timeout_ms: int = 20_000,
    ) -> None:
        self.redis = redis
        self.validate_interval = int(validate_interval_seconds)
        self.max_scrapes_per_run = max(1, int(max_scrapes_per_run))
        self.concurrency = max(1, int(concurrency))
        self.min_rescrape_seconds = int(min_rescrape_seconds)
        self.nav_timeout_ms = int(nav_timeout_ms)
        self.networkidle_timeout_ms = int(networkidle_timeout_ms)

    @staticmethod
    def _norm_id(mid: str) -> str:
        return (mid or "").strip().strip("/").lower()

    def _card_key(self, mid: str) -> str:
        return self.CARD_KEY_PREFIX + self._norm_id(mid)

    @staticmethod
    def _build_url(mid: str) -> str:
        mid = (mid or "").strip().strip("/")
        return f"https://build.nvidia.com/{mid}"

    async def update_from_model_list(self, model_ids: Iterable[str]) -> None:
        ids = [self._norm_id(x) for x in model_ids if self._norm_id(x)]
        if not ids:
            return

        # Keep stable order but remove dupes
        seen = set()
        ordered: List[str] = []
        for mid in ids:
            if mid in seen:
                continue
            seen.add(mid)
            ordered.append(mid)

        # Mark known
        try:
            await self.redis.sadd(self.KNOWN_SET_KEY, *ordered)  # type: ignore
        except Exception:
            pass

        # ✅ Compute missing + due across ALL ids (not a tiny slice)
        keys = [self._card_key(mid) for mid in ordered]
        vals = await self.redis.mget(keys)

        now = time.time()
        missing: List[str] = []
        due: List[str] = []

        for mid, raw in zip(ordered, vals):
            if not raw:
                missing.append(mid)
                continue
            try:
                obj = json.loads(raw)
                validated_at = float(obj.get("validated_at") or 0)
                if (now - validated_at) >= self.validate_interval:
                    due.append(mid)
            except Exception:
                missing.append(mid)

        plan = (missing + due)[: self.max_scrapes_per_run]

        log.info(
            "[nvidia][registry] ids=%d unique=%d missing=%d due=%d plan=%d cap=%d",
            len(ids), len(ordered), len(missing), len(due), len(plan), self.max_scrapes_per_run
        )

        if not plan:
            return

        await self._scrape_and_store_many(plan)

    async def _weekly_due(self, model_ids: List[str]) -> List[str]:
        keys = [self._card_key(mid) for mid in model_ids]
        vals = await self.redis.mget(keys)

        now = time.time()
        due: List[str] = []

        for mid, raw in zip(model_ids, vals):
            if not raw:
                due.append(mid)
                continue
            try:
                obj = json.loads(raw)
                validated_at = float(obj.get("validated_at") or 0)
            except Exception:
                due.append(mid)
                continue

            # weekly revalidate
            if (now - validated_at) >= self.validate_interval:
                due.append(mid)

        return due

    async def get_tool_support_map(self, model_ids: Iterable[str]) -> Dict[str, Optional[bool]]:
        ids = [self._norm_id(x) for x in model_ids if self._norm_id(x)]
        ids = list(dict.fromkeys(ids))

        out: Dict[str, Optional[bool]] = {}

        # hardcoded overrides first
        for mid in ids:
            if mid in self.HARDCODED_TOOL_SUPPORT:
                out[mid] = bool(self.HARDCODED_TOOL_SUPPORT[mid])

        remaining = [mid for mid in ids if mid not in out]
        if not remaining:
            return out

        keys = [self._card_key(mid) for mid in remaining]
        vals = await self.redis.mget(keys)

        for mid, raw in zip(remaining, vals):
            if not raw:
                out[mid] = None
                continue
            try:
                obj = json.loads(raw)
                out[mid] = obj.get("tool_supported", None)
            except Exception:
                out[mid] = None

        return out

    async def _scrape_and_store_many(self, model_ids: List[str]) -> None:
        if async_playwright is None:
            log.error("[nvidia_cards] Playwright not installed. Install: pip install playwright && playwright install chromium")
            return

        sem = asyncio.Semaphore(self.concurrency)

        async with async_playwright() as p:  # type: ignore
            # headless chromium
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            ctx = await browser.new_context(
                viewport={"width": 1400, "height": 900},
                user_agent=self.DEFAULT_UA,
            )

            try:
                await asyncio.gather(
                    *[self._scrape_one(mid, sem, ctx) for mid in model_ids],
                    return_exceptions=True,
                )
            finally:
                await ctx.close()
                await browser.close()

    async def _scrape_one(self, model_id: str, sem: asyncio.Semaphore, ctx) -> None:
        mid = self._norm_id(model_id)
        if not mid:
            return

        # hardcoded always wins (also saves scrape cost)
        if mid in self.HARDCODED_TOOL_SUPPORT:
            await self._store_record(
                mid,
                tool_supported=bool(self.HARDCODED_TOOL_SUPPORT[mid]),
                evidence=[f"hardcoded:{self.HARDCODED_TOOL_SUPPORT[mid]}"],
                url=self._build_url(mid),
                status_code=200,
                html_len=0,
            )
            log.info("[nvidia_cards] %s tool_supported=%s (hardcoded)", mid, self.HARDCODED_TOOL_SUPPORT[mid])
            return

        # skip if scraped recently (< min_rescrape_seconds)
        existing = await self.redis.get(self._card_key(mid))
        if existing:
            try:
                obj = json.loads(existing)
                validated_at = float(obj.get("validated_at") or 0)
                if validated_at and (time.time() - validated_at) < self.min_rescrape_seconds:
                    log.info("[nvidia_cards] %s skip (fresh cache %.0fs ago)", mid, time.time() - validated_at)
                    return
            except Exception:
                pass

        async with sem:
            url = self._build_url(mid)
            page = await ctx.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=self.nav_timeout_ms)
                try:
                    await page.wait_for_load_state("networkidle", timeout=self.networkidle_timeout_ms)
                except PWTimeout:
                    pass

                # Tools button (robust)
                tools_btn = page.get_by_role("button", name=re.compile(r"^Tools$", re.I))
                tools_count = await tools_btn.count()

                tools_found = tools_count > 0
                tools_disabled: Optional[bool] = None
                tools_outer: Optional[str] = None

                if tools_found:
                    try:
                        tools_disabled = await tools_btn.first.is_disabled()
                    except Exception:
                        tools_disabled = None

                    try:
                        tools_outer = await tools_btn.first.evaluate("(el) => el.outerHTML")
                    except Exception:
                        tools_outer = None

                # Wrench presence (icon)
                wrench = page.locator(
                    'svg[data-icon-name="wrench"], '
                    'svg[data-src*="wrench.svg"], '
                    'use[href^="#wrench_"], '
                    'symbol[id^="wrench_"]'
                )
                wrench_count = await wrench.count()
                wrench_found = wrench_count > 0

                # Decide
                tool_supported: Optional[bool]
                evidence: List[str] = [
                    f"tools_found={tools_found}",
                    f"tools_disabled={tools_disabled}",
                    f"wrench_found={wrench_found}",
                    f"wrench_count={wrench_count}",
                ]
                if tools_outer:
                    evidence.append(f"tools_outer_html={tools_outer[:800]}")

                if tools_found and (tools_disabled is False) and wrench_found:
                    tool_supported = True
                elif tools_found and (tools_disabled is True):
                    tool_supported = False
                else:
                    # Page loaded fine; "Tools" missing => no tool calling
                    tool_supported = False

                await self._store_record(
                    mid,
                    tool_supported=tool_supported,
                    evidence=evidence,
                    url=url,
                    status_code=200,
                    html_len=0,
                )

                log.info(
                    "[nvidia_cards] %s tool_supported=%s tools_found=%s disabled=%s wrench=%s(%d)",
                    mid, tool_supported, tools_found, tools_disabled, wrench_found, wrench_count
                )

            except Exception as e:
                log.warning("[nvidia_cards] scrape failed for %s: %s", mid, e)
                # store a failure marker so we don't retry every run
                await self._store_record(
                    mid,
                    tool_supported=None,
                    evidence=[f"error:{type(e).__name__}:{e}"],
                    url=url,
                    status_code=0,
                    html_len=0,
                )
            finally:
                await page.close()

    async def _store_record(
        self,
        model_id: str,
        *,
        tool_supported: Optional[bool],
        evidence: List[str],
        url: str,
        status_code: int,
        html_len: int,
    ) -> None:
        now = time.time()
        obj: Dict[str, Any] = {
            "model_id": model_id,
            "tool_supported": tool_supported,  # True/False/None
            "evidence": (evidence or [])[:30],
            "url": url,
            "status_code": int(status_code),
            "html_len": int(html_len),
            "validated_at": now,
        }
        await self.redis.set(self._card_key(model_id), json.dumps(obj))