from __future__ import annotations

import asyncio
import logging

import asyncpg
from redis.asyncio import Redis

from src.agent_service.core.config import POSTGRES_DSN, REDIS_URL
from src.common.memgraph_mgr import memgraph_mgr
from src.common.milvus_mgr import milvus_mgr

from .service import RouterService

log = logging.getLogger("router_worker")

JOBS_STREAM = "router:jobs"
GROUP = "router_group"
CONSUMER = "router_1"

_UPDATE_ROUTER_SQL = """
UPDATE eval_traces SET
    router_backend         = $1,
    router_sentiment       = $2,
    router_sentiment_score = $3,
    router_reason          = $4,
    router_reason_score    = $5,
    router_override        = $6,
    updated_at             = NOW()
WHERE trace_id = $7
"""


async def ensure_group(r: Redis):
    try:
        await r.xgroup_create(JOBS_STREAM, GROUP, id="0-0", mkstream=True)
    except Exception:
        pass


async def run_worker():
    await memgraph_mgr.connect()
    await milvus_mgr.aconnect()
    log.info("Router worker: Memgraph and Milvus connected.")

    pool: asyncpg.Pool | None = None
    if POSTGRES_DSN:
        pool = await asyncpg.create_pool(POSTGRES_DSN, min_size=1, max_size=5, command_timeout=30)
        log.info("Router worker: PostgreSQL pool connected.")
    else:
        log.warning("Router worker: POSTGRES_DSN not set; router result persistence disabled.")

    r = Redis.from_url(REDIS_URL, decode_responses=True)
    await ensure_group(r)

    router = RouterService()

    while True:
        try:
            resp = await r.xreadgroup(
                groupname=GROUP,
                consumername=CONSUMER,
                streams={JOBS_STREAM: ">"},
                count=25,
                block=15000,
            )
            if not resp:
                continue

            for _stream, entries in resp:
                for msg_id, fields in entries:
                    try:
                        trace_id = fields.get("trace_id")
                        text = fields.get("text") or ""
                        result = await router.classify_embeddings(text)

                        if pool and trace_id:
                            await pool.execute(
                                _UPDATE_ROUTER_SQL,
                                result.backend,
                                result.sentiment.label,
                                float(result.sentiment.score),
                                (result.reason.label if result.reason else None),
                                (float(result.reason.score) if result.reason else None),
                                result.override,
                                trace_id,
                            )

                        await r.xack(JOBS_STREAM, GROUP, msg_id)
                    except Exception as e:
                        log.error("job failed: %s", e)
                        # don't ack -> will be pending; handle with XAUTOCLAIM later
        except Exception as e:
            log.error("worker loop error: %s", e)
            await asyncio.sleep(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())
