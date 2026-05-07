"""One-shot: drop + (re)create the ``inline_guard_cache`` Milvus collection.

The collection is created lazily on first insert by langchain-milvus, so
"creating" it here just means dropping the old one (if present) and letting
the warmup script populate it.

Run once per environment when:
- Adopting the inline-guard vector cache for the first time.
- Bumping ``LOCAL_EMBEDDER_VERSION`` so the dim or schema changes.
- Recovering from a corrupt collection.

Usage:

    docker exec mft_agent python -m scripts.rebuild_inline_guard_cache_collection

Idempotent: dropping a non-existent collection is a no-op.
"""

from __future__ import annotations

import logging
import os
import sys

from pymilvus import MilvusClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent_service.core.config import MILVUS_URI  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("rebuild_inline_guard_cache")

_MILVUS_TOKEN = os.environ.get("MILVUS_TOKEN", "").strip() or None
_COLLECTION_NAME = "inline_guard_cache"


def _drop_collection() -> None:
    conn_args: dict = {"uri": MILVUS_URI}
    if _MILVUS_TOKEN:
        conn_args["token"] = _MILVUS_TOKEN
    client = MilvusClient(**conn_args)
    if client.has_collection(_COLLECTION_NAME):
        log.info("Dropping existing collection %s…", _COLLECTION_NAME)
        client.drop_collection(_COLLECTION_NAME)
        log.info("Dropped %s.", _COLLECTION_NAME)
    else:
        log.info("No collection named %s present — nothing to drop.", _COLLECTION_NAME)


def main() -> None:
    log.info("Inline-guard cache rebuild — Milvus URI %s", MILVUS_URI)
    _drop_collection()
    log.info(
        "Rebuild complete. The collection will be recreated on the first insert "
        "from `make warmup-inline-guard-cache` or the first cache miss in prod."
    )


if __name__ == "__main__":
    main()
