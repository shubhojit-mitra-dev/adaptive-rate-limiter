# Phase 1: Baseline Distributed Rate Limiter MVP

## 1. Overview & Objective

The objective of **Phase 1** is to build, verify, and empirically benchmark a standard, production-ready distributed rate limiter using the **Token Bucket** algorithm, **FastAPI**, and **Redis**.

Before introducing distributed token leasing, bidirectional gRPC streaming, or dynamic AIMD congestion control, we must establish a working baseline. This phase provides the foundation against which all future architectural optimizations will be evaluated.

---

## 2. Architecture & Data Flow

In Phase 1, the system operates as a classic distributed rate-limiting proxy/middleware:

```
[ Incoming HTTP Client ]
           │
           ▼
 [ FastAPI Gateway / Middleware ]
           │
           ├─ 1. Extract API Key (or Client IP)
           ├─ 2. Query Redis for bucket state (tokens, last_refill_timestamp)
           ├─ 3. Calculate replenished tokens based on elapsed time (Delta T * Rate)
           ├─ 4. If tokens >= 1:
           │        - Decrement token count in Redis
           │        - Allow request, return 200 OK + RateLimit headers
           └─ 5. If tokens < 1:
                    - Deny request, return 429 Too Many Requests + Retry-After
```

---

## 3. Scope & Deliverables

1. **Pure Token Bucket Domain Model (`rate_limiter.domain`):**
   - Pure, deterministic calculation of token replenishment and consumption without external I/O dependencies.
   - Support for burst capacity ($B$) and steady-state refill rate ($R\text{ tokens/sec}$).
   - Strict immutability and mathematical precision.

2. **Redis Storage Backend (`rate_limiter.infrastructure.redis`):**
   - Asynchronous Redis client adapter using `redis-py` async.
   - State representation per tenant key: `{tokens: float, last_refill: float}` with appropriate TTL eviction.

3. **FastAPI Middleware / Dependency (`rate_limiter.api`):**
   - ASGI-compatible middleware intercepting incoming requests.
   - Client identification via `X-API-Key` header with fallback to client IP.
   - Standard HTTP headers:
     - `X-RateLimit-Limit`: Maximum burst capacity.
     - `X-RateLimit-Remaining`: Tokens currently available.
     - `X-RateLimit-Reset`: Milliseconds/seconds until the bucket fully refills.
     - `Retry-After`: Returned on HTTP 429 indicating wait time.

4. **Benchmarking & Profiling Harness:**
   - Automated stress script that simulates concurrent clients.
   - Quantifies the baseline p50, p95, and p99 latency overhead introduced by the per-request Redis network call.
   - Demonstrates the Redis IOPS ceiling and race conditions that emerge under concurrent bursts without atomic Lua or token leasing.

---

## 4. Acceptance Criteria & Verification

- [ ] All unit and integration tests pass with $>95\%$ branch coverage.
- [ ] Requests below threshold receive `200 OK` with accurate `X-RateLimit-*` headers.
- [ ] Requests exceeding threshold immediately receive `429 Too Many Requests` with a valid `Retry-After` header.
- [ ] Refill behavior verified across simulated elapsed time intervals.
- [ ] Baseline performance benchmark document recorded with exact p50/p95/p99 latency metrics.
