# Walkthrough: Subphase 1.2 — Redis Storage Adapter & State Synchronization

## 1. Executive Summary

In **Subphase 1.2**, we implemented the asynchronous persistence layer for the distributed rate limiter by engineering the `RedisStorageBackend` adapter. This adapter bridges our pure domain model (`TokenBucketEngine`) with Redis as a distributed state store.

Key achievements:
- Implemented the `RateLimitStorageBackend` abstract protocol adhering to the Dependency Inversion Principle (DIP).
- Engineered dynamic key TTL eviction ($TTL = \max(60, \lceil \frac{\text{capacity}}{\text{refill\_rate}} \rceil \times 2)$) ensuring inactive tenant keys are automatically evicted by Redis without leaking server memory.
- Unified state persistence using Redis Hashes (`tokens`, `last_refill`) batched with `EXPIRE` via Redis pipelines.
- Implemented comprehensive integration test suite using `fakeredis` async, achieving 100% test pass rate across 16 total test cases.

---

## 2. Git Diff & Changed Files Overview

Across branch `feat/subphase-1.2-redis-storage-adapter`:
- Total files modified/added: 7 files

| File Path | Purpose |
| :--- | :--- |
| `src/rate_limiter/infrastructure/redis.py` | `RateLimitStorageBackend` protocol and `RedisStorageBackend` async adapter with pipelined HSET/EXPIRE. |
| `src/rate_limiter/infrastructure/__init__.py` | Infrastructure package exports. |
| `tests/integration/test_redis_storage.py` | Integration test suite covering empty-key initialization, sequential quota consumption, time-decay refills, multi-tenant isolation, and corrupted state handling. |
| `docs/phases/phase-1/subphase-1.2.md` | Specification document for Subphase 1.2. |
| `docs/progress.md` | Updated roadmap and progress milestones. |
| `pyproject.toml` | Added `redis` and `fakeredis` dependencies. |
| `uv.lock` | Locked pinned versions for dependencies. |

---

## 3. Guided PR Reading Order

To systematically review the implementation, inspect the files in this order:

1. **Start with the integration tests:** [`tests/integration/test_redis_storage.py`](../../tests/integration/test_redis_storage.py)
   - Inspect the `fake_redis` and `storage` async fixtures.
   - Read `test_initial_request_initializes_state`: observe how an uninitialized key defaults to capacity and sets a positive TTL.
   - Read `test_sequential_requests_decrement_quota` and `test_exhaustion_denies_request_without_corrupting_state`.
   - Read `test_time_decay_refill_persists_to_redis`: observe time progression across storage writes.
   - Read `test_multi_tenant_isolation`: verify key prefix separation between distinct callers.

2. **Next, inspect the protocol definition:** [`src/rate_limiter/infrastructure/redis.py`](../../src/rate_limiter/infrastructure/redis.py#L18-L38)
   - Read `RateLimitStorageBackend`: abstract protocol decoupling storage from domain logic.

3. **Inspect the Redis adapter implementation:** [`src/rate_limiter/infrastructure/redis.py`](../../src/rate_limiter/infrastructure/redis.py#L41-L176)
   - Read `calculate_ttl()`: inspect the dynamic TTL derivation formula.
   - Read `set_state()`: notice the pipeline context manager batching `hset` and `expire`.
   - Read `evaluate()`: observe how domain calculations integrate with persistence.

---

## 4. Deep Engineering Concepts & Explanations

### A. Memory Leak Prevention via Dynamic TTL Derivation
```python
@staticmethod
def calculate_ttl(rule: RateLimitRule) -> int:
    time_to_fill = rule.capacity / rule.refill_rate
    return max(60, math.ceil(time_to_fill * 2))
```
- **The Problem:** In multi-tenant systems, thousands of unique IP addresses or ephemeral API keys access the ingress daily. If rate limit keys are stored indefinitely without expiration, Redis RAM grows monotonically until Out-Of-Memory (OOM) crashes the cluster.
- **The Solution:** A bucket that is full requires no state tracking because an absent key is mathematically equivalent to a full bucket. By computing the maximum time required to refill from empty to full ($B / R$), doubling it as a safety buffer, and applying it as an `EXPIRE` TTL, Redis automatically garbage-collects idle tenant keys.

### B. Pipelined Atomic Dispatches
```python
async with self._client.pipeline(transaction=True) as pipe:
    pipe.hset(redis_key, mapping=mapping)
    pipe.expire(redis_key, ttl_seconds)
    await pipe.execute()
```
- In naive implementations, developers issue `await client.hset(...)` followed by `await client.expire(...)`. This introduces two separate network round-trips.
- By wrapping both commands in `client.pipeline(transaction=True)`, Redis buffers the commands and executes them atomically within a single `MULTI/EXEC` transaction block, cutting socket write overhead in half.

### C. The Read-Then-Write Baseline for Phase 2
- Notice that in this Phase 1 adapter, `evaluate()` fetches state via `get_state()`, computes new tokens in Python memory, and then writes back via `set_state()`.
- This is intentional: it represents the classic distributed rate limiter architecture. Under high concurrency across multiple workers, this creates an inherent check-then-act race window. In Subphase 1.4, we will load test this exact implementation to demonstrate the race condition and Redis network latency penalty, directly justifying Phase 2's atomic Lua script (`EVALSHA`).
