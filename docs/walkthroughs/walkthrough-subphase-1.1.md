# Walkthrough: Subphase 1.1 — Core Token Bucket Algorithm & State Model

## 1. Executive Summary

In **Subphase 1.1**, we implemented the pure domain core of the Token Bucket rate limiter following strict Test-Driven Development (TDD). The algorithm is completely isolated from network I/O, Redis, and ASGI frameworks, ensuring that mathematical calculations for token consumption, continuous time-decay replenishment, and clock-skew defenses can be verified deterministically with sub-millisecond execution.

All 9 unit tests pass with 100% coverage.

---

## 2. Git Diff & Changed Files Overview

Across branch `feat/subphase-1.1-token-bucket-core`:
- Total files changed: 5 files
- Total lines: +306 insertions, 0 deletions

| File Path | Purpose |
| :--- | :--- |
| `tests/unit/test_token_bucket.py` | Unit test suite covering burst exhaustion, fractional time refills, multi-token costs, and clock drift. |
| `src/rate_limiter/domain/token_bucket.py` | Core domain entities (`RateLimitRule`, `BucketState`, `RateLimitResult`) and algorithmic engine (`TokenBucketEngine`). |
| `src/rate_limiter/domain/__init__.py` | Domain package exports. |
| `src/rate_limiter/__init__.py` | Top-level package initialization and version. |
| `pyproject.toml` | Configured `[tool.pytest.ini_options]` with `pythonpath = ["src"]` and asyncio strict mode. |

---

## 3. Guided PR Reading Order

To review the code systematically, inspect the files in this exact sequence:

1. **Start with the tests:** [`tests/unit/test_token_bucket.py`](../../tests/unit/test_token_bucket.py)
   - First, inspect `MockClock`: see how time is artificially controlled without `time.sleep()`.
   - Read `TestTokenBucketValidation`: inspect invariant checks for positive capacity, rate, and non-negative cost.
   - Read `TestTokenBucketConsumption`: inspect sequential exhaustion and rejection semantics.
   - Read `TestTokenBucketRefill`: inspect fractional token replenishment and clock skew tests.

2. **Next, inspect the domain contracts:** [`src/rate_limiter/domain/token_bucket.py`](../../src/rate_limiter/domain/token_bucket.py#L1-L45)
   - Read `RateLimitRule`, `BucketState`, and `RateLimitResult`.
   - Note the usage of `@dataclass(frozen=True, slots=True)`.

3. **Finally, inspect the algorithmic engine:** [`src/rate_limiter/domain/token_bucket.py`](../../src/rate_limiter/domain/token_bucket.py#L48-L115)
   - Read `TokenBucketEngine.consume()`.
   - Observe how $\Delta t$, refill capping, and `retry_after` are computed.

---

## 4. Deep Engineering Concepts & Explanations

### A. Memory Layout & Hot-Path Performance: `@dataclass(frozen=True, slots=True)`
```python
@dataclass(frozen=True, slots=True)
class BucketState:
    tokens: float
    last_refill_timestamp: float
```
- **Why `slots=True`?** By default, Python objects store their attributes in an internal dictionary (`__dict__`). For an ingress rate limiter processing 20,000+ operations/second, generating and reading `__dict__` introduces memory bloat and dictionary hashing lookups. Using `__slots__` allocates a fixed array of pointers in C memory, drastically reducing per-instance memory footprint and accelerating attribute access.
- **Why `frozen=True`?** Immutability guarantees that domain state cannot be modified by side effects across asynchronous execution points. State transitions must explicitly produce a *new* instance of `BucketState`.

### B. Continuous Time-Decay Refill vs. Timer Ticks
Rather than running an active background thread or periodic ticker to add tokens (which wastes CPU and suffers from event-loop jitter), the token bucket uses **lazy time-decay evaluation**:
$$\Delta t = \max(0.0, T_{\text{now}} - T_{\text{last}})$$
$$\text{Tokens}_{\text{available}} = \min(B, S_{\text{tokens}} + (\Delta t \times R))$$
Tokens are only computed on-demand at the exact instant an evaluation request arrives.

### C. Clock Drift & NTP Backward Skew Protection
```python
elapsed = max(0.0, current_timestamp - state.last_refill_timestamp)
effective_timestamp = max(state.last_refill_timestamp, current_timestamp)
```
In distributed cloud environments, servers periodically synchronize clocks via NTP (Network Time Protocol), which can step the system clock backwards by several milliseconds or seconds.
- Without `max(0.0, ...)`, $\Delta t$ would become negative, causing available tokens to shrink or become negative.
- Using `effective_timestamp = max(...)` ensures that if time moves backwards, the bucket's timestamp baseline does not regress, completely protecting against token anomalies.

### D. Mathematical Calculation of `retry_after` and `reset_after`
When a client is rejected, returning HTTP 429 without guidance causes aggressive retry loops. We compute:
$$\text{Deficit} = \text{Cost} - \text{Tokens}_{\text{available}}$$
$$\text{Retry-After} = \frac{\text{Deficit}}{R}$$
This informs the caller of the exact fractional second needed until sufficient tokens exist to satisfy their request.

