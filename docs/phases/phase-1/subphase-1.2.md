# Subphase 1.2: Redis Storage Adapter & State Synchronization

## 1. Goal & Architectural Role

The goal of **Subphase 1.2** is to build the asynchronous persistence layer that connects our pure domain `TokenBucketEngine` (from Subphase 1.1) to **Redis**.

In accordance with the Dependency Inversion Principle (DIP) and Hexagonal Architecture, high-level business rules must not depend directly on low-level Redis I/O. We define an abstract storage protocol (`RateLimitStorageBackend`) and implement the concrete `RedisStorageBackend` as an infrastructure adapter.

---

## 2. Technical Specification

### 2.1 Storage Contract (`RateLimitStorageBackend`)

```python
class RateLimitStorageBackend(Protocol):
    async def get_state(self, key: str) -> Optional[BucketState]:
        ...

    async def set_state(self, key: str, state: BucketState, ttl_seconds: int) -> None:
        ...

    async def evaluate(
        self,
        key: str,
        rule: RateLimitRule,
        cost: float = 1.0,
        current_timestamp: Optional[float] = None,
    ) -> RateLimitResult:
        ...
```

### 2.2 Redis Schema & TTL Eviction

- **Key Pattern:** `rate_limit:{key}` (e.g., `rate_limit:client_abc123` or `rate_limit:ip_192.168.1.1`).
- **Data Structure:** Redis Hash (`HGETALL` / `HSET`)
  - `tokens`: Float serialized as string (e.g. `"9.0"`).
  - `last_refill`: Unix timestamp in seconds serialized as string (e.g. `"1700000000.123"`).
- **TTL Eviction Strategy:**
  - Inactive tenant keys must not leak Redis memory indefinitely.
  - The TTL is dynamically computed as:
    $$TTL = \max\left(60, \left\lceil \frac{\text{capacity}}{\text{refill\_rate}} \right\rceil \times 2\right)$$
  - Once a bucket has reached full capacity and remains untouched for this TTL duration, Redis automatically evicts the key. Upon the client's next request, the absence of the key defaults to full capacity.

### 2.3 Evaluation Flow (Phase 1 Baseline Mechanics)

```
[ Incoming Request for Key 'tenant_x' ]
                    │
                    ▼
      HGETALL "rate_limit:tenant_x"
                    │
           ┌────────┴────────┐
        (Found)         (Not Found)
           │                 │
  Parse BucketState    Initialize full capacity
           │                 │
           └────────┬────────┘
                    ▼
    TokenBucketEngine.consume(rule, state, cost, now)
                    │
                    ▼
       HSET "rate_limit:tenant_x"
       EXPIRE "rate_limit:tenant_x" TTL
                    │
                    ▼
          Return RateLimitResult
```

> [!NOTE]
> This two-step `HGETALL` $\rightarrow$ `HSET` sequence in Phase 1 provides our exact baseline. It directly exposes the network round-trip overhead and concurrent race conditions that we will empirically measure in Subphase 1.4, directly justifying Phase 2's atomic Lua script (`EVALSHA`).

---

## 3. Test-Driven Development Plan

1. **Integration Test Suite (`tests/integration/test_redis_storage.py`):**
   - Test initial request on empty key initializes bucket to full capacity.
   - Test sequential requests decrement tokens and update timestamp in Redis.
   - Test multi-tenant key isolation (evaluating tenant A does not affect tenant B).
   - Test TTL persistence (ensuring `EXPIRE` is set on every update).
   - Test rejection when bucket is exhausted.
   - Test custom timestamp injection for deterministic time simulation.
2. **Implementation (`src/rate_limiter/infrastructure/redis.py`):**
   - Implement `RedisStorageBackend` with async connection management, safe serialization/deserialization, and automatic resource cleanup.
3. **Verification:**
   - Run complete test suite and verify 100% pass rate.
