# Subphase 1.1: Core Token Bucket Algorithm & State Model

## 1. Goal & Architectural Focus

The goal of **Subphase 1.1** is to design and implement the pure domain core of the **Token Bucket** algorithm following strict Test-Driven Development (TDD).

To ensure high maintainability and testability (Clean Architecture / Hexagonal Architecture), the core algorithm must be completely decoupled from any external storage (Redis) or web framework (FastAPI). It must be a pure, deterministic state machine operating solely on timestamps and token arithmetic.

---

## 2. Technical Specification

### 2.1 Domain Entities

1. **`RateLimitRule`:**
   - `capacity: float` (Maximum burst tokens available in the bucket, $B$)
   - `refill_rate: float` (Tokens replenished per second, $R$)

2. **`BucketState`:**
   - `tokens: float` (Current available tokens)
   - `last_refill_timestamp: float` (Unix epoch timestamp of last calculation)

3. **`RateLimitResult`:**
   - `allowed: bool` (Whether the request is permitted)
   - `limit: float` (Total bucket capacity)
   - `remaining: float` (Available tokens remaining after this operation)
   - `reset_after: float` (Seconds until bucket is fully restored to capacity)
   - `retry_after: Optional[float]` (Seconds caller must wait before retrying, populated only when `allowed == False`)

### 2.2 Algorithm Mechanics

Given current time $T_{\text{now}}$, previous state $(S_{\text{tokens}}, T_{\text{last}})$, and cost $C$:
1. $\Delta t = \max(0.0, T_{\text{now}} - T_{\text{last}})$ *(Guards against backwards clock drift)*.
2. $\text{Refilled} = \Delta t \times R$.
3. $\text{Current Tokens} = \min(B, S_{\text{tokens}} + \text{Refilled})$.
4. If $\text{Current Tokens} \ge C$:
   - $\text{New Tokens} = \text{Current Tokens} - C$
   - $\text{allowed} = \text{True}$
   - $\text{retry\_after} = \text{None}$
5. Else:
   - $\text{New Tokens} = \text{Current Tokens}$
   - $\text{allowed} = \text{False}$
   - $\text{Deficit} = C - \text{Current Tokens}$
   - $\text{retry\_after} = \frac{\text{Deficit}}{R}$
6. $\text{reset\_after} = \frac{B - \text{New Tokens}}{R}$.

---

## 3. Test-Driven Development Plan

1. **Test Suite First (`tests/unit/test_token_bucket.py`):**
   - Test burst consumption up to capacity.
   - Test denial when tokens are exhausted, verifying accurate `retry_after` calculation.
   - Test time-decay refill over fractional seconds using deterministic simulated clocks.
   - Test capacity capping (ensuring tokens never exceed max capacity).
   - Test multi-token costs ($C > 1$).
   - Test zero or negative elapsed time handling (clock skew protection).
2. **Implementation (`src/rate_limiter/domain/token_bucket.py`):**
   - Write clean, type-annotated, pure Python domain classes and evaluation function.
3. **Verification:**
   - Verify 100% test pass rate with pytest.

