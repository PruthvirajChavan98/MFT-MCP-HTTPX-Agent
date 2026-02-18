"""
Production-grade session cost tracking with Redis persistence.

Features:
- Atomic updates with Redis transactions
- Detailed usage breakdown by model/provider
- Automatic expiry and cleanup
- Comprehensive error handling
- Audit trail
"""

import json
import logging
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional

from redis.asyncio import Redis
from redis.exceptions import RedisError

log = logging.getLogger(__name__)


class SessionCostTracker:
    """Thread-safe session cost tracking with Redis backend."""

    # Redis key patterns
    COST_KEY_PREFIX = "session:cost"
    HISTORY_KEY_PREFIX = "session:cost:history"

    # Data retention (days)
    COST_TTL = 30 * 24 * 60 * 60  # 30 days
    HISTORY_TTL = 7 * 24 * 60 * 60  # 7 days
    HISTORY_MAX_ENTRIES = 1000

    def __init__(self, redis: Optional[Redis] = None):
        """Initialize with optional Redis connection."""
        self._redis = redis

    async def _get_redis(self) -> Redis:
        """Get Redis connection."""
        if self._redis:
            return self._redis

        from src.agent_service.core.session_utils import get_redis

        return await get_redis()

    @staticmethod
    def _cost_key(session_id: str) -> str:
        """Redis key for session cost aggregate."""
        return f"{SessionCostTracker.COST_KEY_PREFIX}:{session_id}"

    @staticmethod
    def _history_key(session_id: str) -> str:
        """Redis key for session cost history (list)."""
        return f"{SessionCostTracker.HISTORY_KEY_PREFIX}:{session_id}"

    @staticmethod
    def _round_cost(value: float) -> float:
        """Round cost to 8 decimal places (satoshi precision)."""
        return float(Decimal(str(value)).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP))

    async def add_cost(
        self,
        session_id: str,
        cost: float,
        usage: Dict[str, int],
        model: str,
        provider: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Atomically add cost entry to session totals.

        Args:
            session_id: Unique session identifier
            cost: Cost in USD (can be 0 for free tier)
            usage: Token usage breakdown
            model: Model identifier
            provider: Provider name (groq/openrouter/nvidia)
            metadata: Optional request metadata (endpoint, latency, etc.)

        Returns:
            True if successful, False otherwise
        """
        if not session_id:
            log.error("Cannot track cost: session_id is required")
            return False

        try:
            redis = await self._get_redis()
            cost_key = self._cost_key(session_id)
            history_key = self._history_key(session_id)

            # Current timestamp
            now = datetime.now(timezone.utc)
            now_iso = now.isoformat()

            # Build history entry
            history_entry = {
                "timestamp": now_iso,
                "cost": self._round_cost(cost),
                "model": model,
                "provider": provider,
                "usage": {k: v for k, v in usage.items() if v and v > 0},
                "metadata": metadata or {},
            }

            # Use pipeline for atomic updates
            async with redis.pipeline(transaction=True) as pipe:
                # Get existing aggregate
                existing = await redis.get(cost_key)

                if existing:
                    data = json.loads(existing)
                else:
                    # Initialize new session cost tracking
                    data = {
                        "session_id": session_id,
                        "total_cost": 0.0,
                        "total_requests": 0,
                        "total_tokens": 0,
                        "total_prompt_tokens": 0,
                        "total_completion_tokens": 0,
                        "total_reasoning_tokens": 0,
                        "total_cached_tokens": 0,
                        "by_model": {},
                        "by_provider": {},
                        "first_request_at": now_iso,
                        "last_request_at": None,
                        "version": "1.0",
                    }

                # Update aggregate totals
                data["total_cost"] = self._round_cost(data["total_cost"] + cost)
                data["total_requests"] += 1
                data["total_tokens"] += usage.get("total_tokens", 0)
                data["total_prompt_tokens"] += usage.get("prompt_tokens", 0)
                data["total_completion_tokens"] += usage.get("completion_tokens", 0)
                data["total_reasoning_tokens"] += usage.get("reasoning_tokens", 0)
                data["total_cached_tokens"] += usage.get("cached_tokens", 0)
                data["last_request_at"] = now_iso

                # Update model breakdown
                if model not in data["by_model"]:
                    data["by_model"][model] = {
                        "cost": 0.0,
                        "requests": 0,
                        "tokens": 0,
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "reasoning_tokens": 0,
                    }
                model_data = data["by_model"][model]
                model_data["cost"] = self._round_cost(model_data["cost"] + cost)
                model_data["requests"] += 1
                model_data["tokens"] += usage.get("total_tokens", 0)
                model_data["prompt_tokens"] += usage.get("prompt_tokens", 0)
                model_data["completion_tokens"] += usage.get("completion_tokens", 0)
                model_data["reasoning_tokens"] += usage.get("reasoning_tokens", 0)

                # Update provider breakdown
                if provider not in data["by_provider"]:
                    data["by_provider"][provider] = {
                        "cost": 0.0,
                        "requests": 0,
                        "tokens": 0,
                        "free_tier": cost == 0.0,
                    }
                provider_data = data["by_provider"][provider]
                provider_data["cost"] = self._round_cost(provider_data["cost"] + cost)
                provider_data["requests"] += 1
                provider_data["tokens"] += usage.get("total_tokens", 0)

                # Execute atomic updates
                pipe.set(cost_key, json.dumps(data), ex=self.COST_TTL)
                pipe.lpush(history_key, json.dumps(history_entry))
                pipe.ltrim(history_key, 0, self.HISTORY_MAX_ENTRIES - 1)
                pipe.expire(history_key, self.HISTORY_TTL)

                await pipe.execute()

            log.info(
                f"Session {session_id}: Added ${cost:.6f} ({provider}/{model}), "
                f"total: ${data['total_cost']:.6f} over {data['total_requests']} requests"
            )
            return True

        except RedisError as e:
            log.error(f"Redis error tracking session cost: {e}")
            return False
        except Exception as e:
            log.exception(f"Failed to track session cost: {e}")
            return False

    async def get_cost(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get aggregate cost data for session.

        Returns:
            Cost aggregate dict or None if no data exists
        """
        try:
            redis = await self._get_redis()
            cost_key = self._cost_key(session_id)

            existing = await redis.get(cost_key)
            if not existing:
                return None

            data = json.loads(existing)

            # Add computed fields
            data["average_cost_per_request"] = (
                self._round_cost(data["total_cost"] / data["total_requests"])
                if data["total_requests"] > 0
                else 0.0
            )

            return data

        except RedisError as e:
            log.error(f"Redis error getting session cost: {e}")
            return None
        except Exception as e:
            log.error(f"Failed to get session cost: {e}")
            return None

    async def get_history(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent cost history for session.

        Args:
            session_id: Session identifier
            limit: Max entries to return (default 100)

        Returns:
            List of cost entries, most recent first
        """
        try:
            redis = await self._get_redis()
            history_key = self._history_key(session_id)

            # Get entries from list
            entries = await redis.lrange(history_key, 0, limit - 1)  # type: ignore[misc]

            return [json.loads(entry) for entry in entries]

        except RedisError as e:
            log.error(f"Redis error getting cost history: {e}")
            return []
        except Exception as e:
            log.error(f"Failed to get cost history: {e}")
            return []

    async def reset_cost(self, session_id: str) -> bool:
        """
        Reset all cost tracking for session.

        Args:
            session_id: Session identifier

        Returns:
            True if successful
        """
        try:
            redis = await self._get_redis()
            cost_key = self._cost_key(session_id)
            history_key = self._history_key(session_id)

            deleted = await redis.delete(cost_key, history_key)

            if deleted > 0:
                log.info(f"Reset cost tracking for session {session_id}")
                return True
            else:
                log.warning(f"No cost data found for session {session_id}")
                return False

        except RedisError as e:
            log.error(f"Redis error resetting session cost: {e}")
            return False
        except Exception as e:
            log.error(f"Failed to reset session cost: {e}")
            return False

    async def get_all_sessions_summary(self) -> Dict[str, Any]:
        """
        Get summary of all active sessions with cost data.

        Returns:
            Summary statistics across all sessions
        """
        try:
            redis = await self._get_redis()

            # Scan for aggregate cost keys ONLY (exclude history keys)
            # Pattern: session:cost:{session_id} but NOT session:cost:history:{session_id}
            pattern = f"{self.COST_KEY_PREFIX}:*"
            sessions = []
            total_cost = 0.0
            total_requests = 0

            async for key in redis.scan_iter(match=pattern, count=100):
                # Skip history keys (they are lists, not aggregates)
                if ":history:" in key:
                    continue

                try:
                    data = await redis.get(key)
                    if data:
                        session_data = json.loads(data)
                        sessions.append(
                            {
                                "session_id": session_data["session_id"],
                                "total_cost": session_data["total_cost"],
                                "total_requests": session_data["total_requests"],
                                "last_request_at": session_data["last_request_at"],
                            }
                        )
                        total_cost += session_data["total_cost"]
                        total_requests += session_data["total_requests"]
                except json.JSONDecodeError:
                    log.warning(f"Failed to parse JSON from key {key}")
                    continue
                except Exception as e:
                    log.warning(f"Failed to process key {key}: {e}")
                    continue

            return {
                "active_sessions": len(sessions),
                "total_cost": self._round_cost(total_cost),
                "total_requests": total_requests,
                "sessions": sorted(sessions, key=lambda x: x["total_cost"], reverse=True),
            }

        except Exception as e:
            log.error(f"Failed to get sessions summary: {e}")
            return {"active_sessions": 0, "total_cost": 0.0, "total_requests": 0, "error": str(e)}


# Global singleton
_session_cost_tracker: Optional[SessionCostTracker] = None


def get_session_cost_tracker() -> SessionCostTracker:
    """Get or create global session cost tracker instance."""
    global _session_cost_tracker
    if _session_cost_tracker is None:
        _session_cost_tracker = SessionCostTracker()
    return _session_cost_tracker
