from __future__ import annotations

import asyncio
import logging

from redis.asyncio import Redis

from src.agent_service.core.config import REDIS_URL
from src.common.neo4j_mgr import Neo4jManager

from .service import RouterService

log = logging.getLogger("router_worker")

JOBS_STREAM = "router:jobs"
GROUP = "router_group"
CONSUMER = "router_1"


async def ensure_group(r: Redis):
    try:
        await r.xgroup_create(JOBS_STREAM, GROUP, id="0-0", mkstream=True)
    except Exception:
        pass


async def run_worker():
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
                        # embeddings-first; upgrade to hybrid if you want
                        result = await router.classify_embeddings(text)

                        # persist on EvalTrace as TOP-LEVEL props
                        Neo4jManager.execute_write(
                            """
                            MATCH (t:EvalTrace {trace_id:$trace_id})
                            SET t.router_backend = $backend,
                                t.router_sentiment = $sentiment,
                                t.router_sentiment_score = $sent_score,
                                t.router_reason = $reason,
                                t.router_reason_score = $reason_score,
                                t.router_override = $override,
                                t.router_updated_at = datetime()
                            """,
                            {
                                "trace_id": trace_id,
                                "backend": result.backend,
                                "sentiment": result.sentiment.label,
                                "sent_score": float(result.sentiment.score),
                                "reason": (result.reason.label if result.reason else None),
                                "reason_score": (
                                    float(result.reason.score) if result.reason else None
                                ),
                                "override": result.override,
                            },
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
