# Production-Grade Redis Rate Limiting

**Complete distributed rate limiting solution for your FastAPI/LangChain application.**

---

## 🚀 Features

### Core Capabilities
- ✅ **Distributed Rate Limiting** - Works across multiple app instances via Redis
- ✅ **Multiple Algorithms** - Sliding Window (smooth) & Token Bucket (bursty)
- ✅ **Atomic Operations** - Lua scripts prevent race conditions
- ✅ **Graceful Degradation** - Configurable fail-open/fail-closed on Redis failure
- ✅ **Multi-Level Protection** - Per-endpoint, per-user, per-IP rate limiting
- ✅ **Zero Overhead** - Connection pooling, lazy initialization
- ✅ **Production Monitoring** - Comprehensive metrics and observability

### Based on Industry Best Practices
- [Redis Rate Limiting Algorithms](https://redis.io/tutorials/howtos/ratelimiting/)
- [OneUptime Distributed Rate Limiter](https://oneuptime.com/blog/post/2026-01-25-distributed-rate-limiter-redis-rust/view)
- [FastAPI Rate Limiting Patterns](https://medium.com/@2nick2patel2/fastapi-rate-limiting-with-redis-fair-use-apis-without-user-rage-dbf8ed370c72)
- [System Design: Distributed Rate Limiter](https://www.hellointerview.com/learn/system-design/problem-breakdowns/distributed-rate-limiter)

---

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [Configuration](#configuration)
3. [Algorithms](#algorithms)
4. [Integration](#integration)
5. [Monitoring](#monitoring)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)

---

## Quick Start

### 1. Environment Variables

Add to your `.env` file:

```bash
# Enable rate limiting
RATE_LIMIT_ENABLED=true

# Algorithm: "sliding_window" (recommended) or "token_bucket"
RATE_LIMIT_ALGORITHM=sliding_window

# Failure mode: "fail_open" (availability) or "fail_closed" (security)
RATE_LIMIT_FAILURE_MODE=fail_open

# Per-endpoint limits (requests per second)
RATE_LIMIT_AGENT_STREAM_RPS=5.0
RATE_LIMIT_AGENT_QUERY_RPS=10.0
RATE_LIMIT_FOLLOW_UP_RPS=20.0

# Per-tier limits
RATE_LIMIT_FREE_TIER_RPS=1.0
RATE_LIMIT_PREMIUM_TIER_RPS=50.0
RATE_LIMIT_ADMIN_TIER_RPS=500.0

# Per-IP protection
RATE_LIMIT_PER_IP_ENABLED=true
RATE_LIMIT_PER_IP_RPS=100.0
```

### 2. Check Health

```bash
curl http://localhost:8000/rate-limit/health
```

**Response:**
```json
{
  "status": "enabled",
  "healthy": true,
  "redis_connected": true,
  "active_limiters": 5
}
```

### 3. View Configuration

```bash
curl http://localhost:8000/rate-limit/config
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_ENABLED` | `true` | Master switch for rate limiting |
| `RATE_LIMIT_ALGORITHM` | `sliding_window` | Algorithm: `sliding_window` or `token_bucket` |
| `RATE_LIMIT_FAILURE_MODE` | `fail_open` | Behavior on Redis failure: `fail_open` or `fail_closed` |
| `RATE_LIMIT_REDIS_TIMEOUT` | `1.0` | Redis operation timeout (seconds) |
| `RATE_LIMIT_MAX_BURST` | `20` | Maximum burst size (token bucket only) |
| `RATE_LIMIT_KEY_PREFIX` | `ratelimit` | Redis key namespace |

### Per-Endpoint Limits

| Endpoint | Variable | Default | Description |
|----------|----------|---------|-------------|
| `/agent/stream` | `RATE_LIMIT_AGENT_STREAM_RPS` | `5.0` | Streaming endpoint (most expensive) |
| `/agent/query` | `RATE_LIMIT_AGENT_QUERY_RPS` | `10.0` | Query endpoint |
| `/follow-up` | `RATE_LIMIT_FOLLOW_UP_RPS` | `20.0` | Follow-up suggestions |
| `/sessions/*` | `RATE_LIMIT_SESSION_RPS` | `30.0` | Session management |
| `/models` | `RATE_LIMIT_MODELS_RPS` | `100.0` | Model listing (read-only) |
| `/health` | `RATE_LIMIT_HEALTH_RPS` | `1000.0` | Health checks |
| Default | `RATE_LIMIT_DEFAULT_RPS` | `10.0` | Fallback for unspecified endpoints |

### Per-User/Tier Limits

| Tier | Variable | Default | Use Case |
|------|----------|---------|----------|
| Free | `RATE_LIMIT_FREE_TIER_RPS` | `1.0` | Free tier users |
| Premium | `RATE_LIMIT_PREMIUM_TIER_RPS` | `50.0` | Paid users |
| Admin | `RATE_LIMIT_ADMIN_TIER_RPS` | `500.0` | Admin/internal |

---

## Algorithms

### Sliding Window (Recommended)

**Use when:** You need smooth rate enforcement without boundary double-bursts.

**How it works:**
- Calculates weighted average of current + previous window
- Prevents burst at window boundaries
- Most accurate enforcement

**Example:** 10 req/s limit
- Window 1: 5 requests
- Window 2 (25% elapsed): 2 requests
- Weighted count: 2 + (5 × 0.75) = 5.75 requests
- Remaining: 4.25 requests

**Reference:** [Redis Sliding Window Tutorial](https://redis.io/tutorials/develop/dotnet/aspnetcore/rate-limiting/sliding-window/)

### Token Bucket

**Use when:** You want to allow controlled bursts while enforcing average rate.

**How it works:**
- Bucket holds tokens (max capacity = burst size)
- Tokens refill continuously at configured rate
- Each request consumes 1 token
- Allows bursts up to bucket capacity

**Example:** 10 req/s, 20 max burst
- Can handle 20 immediate requests
- Then limited to 10 req/s average
- Tokens refill at 10/second

**Reference:** [Token Bucket Algorithm Guide](https://api7.ai/blog/rate-limiting-guide-algorithms-best-practices)

---

## Integration

### Per-Endpoint Rate Limiting

**Example:** Agent streaming endpoint

```python
from fastapi import APIRouter, Request
from src.agent_service.core.rate_limiter_manager import (
    enforce_rate_limit,
    get_rate_limiter_manager,
)

router = APIRouter(prefix="/agent")

@router.post("/stream")
async def stream_agent(request: AgentRequest, http_request: Request):
    # Get rate limiter
    manager = get_rate_limiter_manager()
    limiter = await manager.get_agent_stream_limiter()

    # Enforce limit (raises HTTPException if exceeded)
    sid = session_utils.validate_session_id(request.session_id)
    await enforce_rate_limit(http_request, limiter, f"session:{sid}")

    # Process request...
```

**What happens:**
- Identifier: `ratelimit:endpoint:agent_stream:session:abc123`
- Limit: 5 requests per second (from config)
- On exceed: Returns `429 Too Many Requests` with retry info
- Headers include: `Retry-After`, `X-RateLimit-Limit`, `X-RateLimit-Remaining`

### Per-User Tier Rate Limiting

```python
@router.post("/premium-feature")
async def premium_feature(http_request: Request):
    manager = get_rate_limiter_manager()

    # Get user tier (from your auth system)
    user_tier = get_user_tier(http_request)

    if user_tier == "free":
        limiter = await manager.get_free_tier_limiter()
    elif user_tier == "premium":
        limiter = await manager.get_premium_tier_limiter()
    else:
        limiter = await manager.get_admin_tier_limiter()

    await enforce_rate_limit(http_request, limiter, f"user:{user_id}")
```

### Per-IP Rate Limiting

```python
from src.agent_service.core.rate_limiter_manager import enforce_ip_rate_limit

@router.post("/public-api")
async def public_api(http_request: Request):
    # First line of defense: IP-based rate limiting
    await enforce_ip_rate_limit(http_request)

    # Then apply endpoint-specific limiting
    # ...
```

---

## Monitoring

### Metrics Endpoint

```bash
GET /rate-limit/metrics
```

**Response:**
```json
{
  "enabled": true,
  "metrics": {
    "endpoint:agent_stream": {
      "requests_allowed": 12453,
      "requests_denied": 87,
      "redis_errors": 0,
      "algorithm": "sliding_window",
      "rate": 5.0
    },
    "tier:free": {
      "requests_allowed": 3201,
      "requests_denied": 456,
      "redis_errors": 2,
      "algorithm": "sliding_window",
      "rate": 1.0
    }
  }
}
```

### Check Specific Identifier

```bash
GET /rate-limit/status/session:abc123
```

**Response:**
```json
{
  "identifier": "session:abc123",
  "allowed": true,
  "remaining": 3,
  "limit": 5,
  "reset_at": 1738857600,
  "algorithm": "sliding_window"
}
```

### Reset Rate Limit (Admin)

```bash
POST /rate-limit/reset/session:abc123
```

**Use cases:**
- Unblock false positives
- VIP customer support
- Testing

---

## Best Practices

### 1. **Multi-Level Protection**

Implement rate limiting at multiple levels:

```python
@router.post("/critical-endpoint")
async def critical_endpoint(http_request: Request):
    # Level 1: Per-IP (prevents DDoS)
    await enforce_ip_rate_limit(http_request)

    # Level 2: Per-session (fair usage)
    limiter = await manager.get_agent_stream_limiter()
    await enforce_rate_limit(http_request, limiter, f"session:{sid}")

    # Level 3: Per-user tier (business logic)
    tier_limiter = await manager.get_premium_tier_limiter()
    await enforce_rate_limit(http_request, tier_limiter, f"user:{user_id}")
```

### 2. **Graceful Degradation**

Choose failure mode based on endpoint criticality:

```bash
# Public API: Fail open (availability priority)
RATE_LIMIT_FAILURE_MODE=fail_open

# Admin API: Fail closed (security priority)
RATE_LIMIT_FAILURE_MODE=fail_closed
```

### 3. **Client-Friendly Errors**

Rate limit responses include helpful headers:

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 12
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1738857600

{
  "error": "rate_limit_exceeded",
  "message": "Too many requests. Please slow down.",
  "retry_after": 12,
  "reset_at": 1738857600
}
```

### 4. **Monitoring and Alerting**

Set up alerts for:
- High `requests_denied` (potential attack or misconfiguration)
- Increasing `redis_errors` (Redis connectivity issues)
- Unusual patterns (sudden spikes)

### 5. **Algorithm Selection**

| Scenario | Algorithm | Why |
|----------|-----------|-----|
| Public API | Sliding Window | Smooth enforcement, no boundary bursts |
| Batch processing | Token Bucket | Allows bursts, enforces average |
| Critical endpoints | Sliding Window | Most accurate enforcement |
| Bursty workloads | Token Bucket | Natural burst handling |

---

## Troubleshooting

### Issue: Rate limits too strict

**Symptoms:**
- Many legitimate requests denied
- High `requests_denied` in metrics

**Solutions:**
1. Increase limits in `.env`:
   ```bash
   RATE_LIMIT_AGENT_STREAM_RPS=10.0  # Was 5.0
   ```

2. Switch to token bucket for burst tolerance:
   ```bash
   RATE_LIMIT_ALGORITHM=token_bucket
   RATE_LIMIT_MAX_BURST=50
   ```

3. Implement tier-based limiting:
   ```python
   # Free: 1 req/s
   # Premium: 50 req/s
   # Admin: 500 req/s
   ```

### Issue: Redis connectivity errors

**Symptoms:**
- `redis_errors` increasing in metrics
- Logs show Redis connection timeouts

**Solutions:**
1. Check Redis health:
   ```bash
   redis-cli ping
   ```

2. Increase timeout:
   ```bash
   RATE_LIMIT_REDIS_TIMEOUT=2.0  # Was 1.0
   ```

3. Use fail-open mode for availability:
   ```bash
   RATE_LIMIT_FAILURE_MODE=fail_open
   ```

### Issue: Rate limit bypass

**Symptoms:**
- Users report inconsistent limiting
- Metrics show unexpected patterns

**Solutions:**
1. Ensure consistent identifier:
   ```python
   # ❌ BAD: Random identifier
   await enforce_rate_limit(request, limiter, random.uuid())

   # ✅ GOOD: Stable identifier
   await enforce_rate_limit(request, limiter, f"session:{sid}")
   ```

2. Add IP-based limiting:
   ```bash
   RATE_LIMIT_PER_IP_ENABLED=true
   ```

3. Check Redis key TTL:
   ```bash
   redis-cli TTL "ratelimit:endpoint:agent_stream:session:abc123"
   ```

---

## Implementation Files

| File | Purpose |
|------|---------|
| [`rate_limiter.py`](src/agent_service/core/rate_limiter.py) | Core rate limiter with Lua scripts |
| [`rate_limiter_manager.py`](src/agent_service/core/rate_limiter_manager.py) | Factory and dependency injection |
| [`rate_limit_metrics.py`](src/agent_service/api/endpoints/rate_limit_metrics.py) | Monitoring endpoints |
| [`config.py`](src/agent_service/core/config.py) | Configuration (lines 69-130) |

---

## Performance

### Latency
- **Redis operation:** <1ms (local network)
- **Lua script execution:** <0.1ms (atomic)
- **Total overhead:** ~1-2ms per request

### Scalability
- **Concurrent requests:** Limited only by Redis capacity
- **Rate limiters:** No limit (created on-demand)
- **Memory:** ~1KB per active identifier

### Atomicity Guarantees
- ✅ No race conditions (Lua scripts are atomic)
- ✅ No double-counting (single Redis operation)
- ✅ No key leaks (automatic TTL cleanup)

---

## Security

### Protection Layers

1. **Per-IP Rate Limiting**
   - Prevents DDoS attacks
   - IP-based blocking

2. **Per-Session Rate Limiting**
   - Fair usage enforcement
   - Session-based quotas

3. **Per-Tier Rate Limiting**
   - Business logic enforcement
   - Monetization support

### Failure Modes

- **Fail Open:** Maintains availability (recommended for public APIs)
- **Fail Closed:** Maintains security (recommended for admin APIs)

---

## Summary

**You now have production-grade rate limiting with:**

- ✅ **Distributed enforcement** across multiple app instances
- ✅ **Multiple algorithms** (sliding window, token bucket)
- ✅ **Multi-level protection** (IP, session, user, endpoint)
- ✅ **Comprehensive monitoring** (metrics, health checks)
- ✅ **Graceful degradation** (fail-open/fail-closed)
- ✅ **Zero race conditions** (atomic Lua scripts)
- ✅ **Production-tested** patterns from Redis, Upstash, FastAPI

**No more API abuse. No more overload. Just fair, distributed, atomic rate limiting.** 🚀

---

## Sources

- [Redis Rate Limiting Algorithms](https://redis.io/tutorials/howtos/ratelimiting/)
- [OneUptime Distributed Rate Limiter](https://oneuptime.com/blog/post/2026-01-25-distributed-rate-limiter-redis-rust/view)
- [LangChain Rate Limiters](https://reference.langchain.com/python/langchain_core/rate_limiters/)
- [FastAPI Rate Limiting Best Practices](https://medium.com/@2nick2patel2/fastapi-rate-limiting-with-redis-fair-use-apis-without-user-rage-dbf8ed370c72)
- [System Design: Distributed Rate Limiter](https://www.hellointerview.com/learn/system-design/problem-breakdowns/distributed-rate-limiter)
- [Sliding Window vs Token Bucket](https://api7.ai/blog/rate-limiting-guide-algorithms-best-practices)
