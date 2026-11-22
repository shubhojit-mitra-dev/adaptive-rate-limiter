"""
Unit test suite for the core Token Bucket rate limiting algorithm.

Following strict Test-Driven Development (TDD):
Validates pure domain arithmetic, burst behavior, time-decay refills,
fractional token replenishment, clock drift protection, and boundary invariants.
"""

from dataclasses import dataclass
import pytest


# We will import these from rate_limiter.domain.token_bucket
from rate_limiter.domain.token_bucket import (
    RateLimitRule,
    BucketState,
    RateLimitResult,
    TokenBucketEngine,
)


class MockClock:
    """Deterministic simulated clock for time-dependent unit tests."""

    def __init__(self, initial_time: float = 1000.0) -> None:
        self._current_time: float = initial_time

    @property
    def now(self) -> float:
        return self._current_time

    def advance(self, seconds: float) -> None:
        self._current_time += seconds


class TestTokenBucketValidation:
    """Validates structural constraints and domain invariants on rules and inputs."""

    def test_invalid_capacity_raises_error(self) -> None:
        with pytest.raises(ValueError, match="Capacity must be strictly positive"):
            RateLimitRule(capacity=0.0, refill_rate=10.0)

        with pytest.raises(ValueError, match="Capacity must be strictly positive"):
            RateLimitRule(capacity=-5.0, refill_rate=10.0)

    def test_invalid_refill_rate_raises_error(self) -> None:
        with pytest.raises(ValueError, match="Refill rate must be strictly positive"):
            RateLimitRule(capacity=10.0, refill_rate=0.0)

        with pytest.raises(ValueError, match="Refill rate must be strictly positive"):
            RateLimitRule(capacity=10.0, refill_rate=-1.0)

    def test_negative_cost_raises_error(self) -> None:
        rule = RateLimitRule(capacity=10.0, refill_rate=5.0)
        state = BucketState(tokens=10.0, last_refill_timestamp=1000.0)
        with pytest.raises(ValueError, match="Cost cannot be negative"):
            TokenBucketEngine.consume(rule, state, cost=-1.0, current_timestamp=1000.0)


class TestTokenBucketConsumption:
    """Validates token consumption, allowance, and rejection semantics."""

    def test_initial_state_allows_consumption(self) -> None:
        rule = RateLimitRule(capacity=10.0, refill_rate=2.0)
        state = BucketState(tokens=10.0, last_refill_timestamp=1000.0)

        result, new_state = TokenBucketEngine.consume(
            rule, state, cost=1.0, current_timestamp=1000.0
        )

        assert result.allowed is True
        assert result.limit == 10.0
        assert result.remaining == 9.0
        assert result.retry_after is None
        assert pytest.approx(result.reset_after, rel=1e-4) == 0.5  # 1 token deficit / 2 tokens/s = 0.5s
        assert new_state.tokens == 9.0
        assert new_state.last_refill_timestamp == 1000.0

    def test_exhaustion_rejects_subsequent_request(self) -> None:
        rule = RateLimitRule(capacity=3.0, refill_rate=1.0)
        clock = MockClock(1000.0)
        state = BucketState(tokens=3.0, last_refill_timestamp=clock.now)

        # Consume 3 tokens sequentially at time = 1000.0
        for _ in range(3):
            result, state = TokenBucketEngine.consume(
                rule, state, cost=1.0, current_timestamp=clock.now
            )
            assert result.allowed is True

        # Bucket should now be exhausted
        assert state.tokens == 0.0

        # 4th request must be rejected
        result, state = TokenBucketEngine.consume(
            rule, state, cost=1.0, current_timestamp=clock.now
        )
        assert result.allowed is False
        assert result.remaining == 0.0
        assert result.retry_after is not None
        assert pytest.approx(result.retry_after, rel=1e-4) == 1.0  # Needs 1 token / 1.0 rate = 1.0s
        assert state.tokens == 0.0  # State remains untouched when denied

    def test_multi_token_cost_consumption(self) -> None:
        rule = RateLimitRule(capacity=10.0, refill_rate=2.0)
        state = BucketState(tokens=10.0, last_refill_timestamp=1000.0)

        # Consuming cost = 4 leaves 6
        result, state = TokenBucketEngine.consume(
            rule, state, cost=4.0, current_timestamp=1000.0
        )
        assert result.allowed is True
        assert result.remaining == 6.0

        # Consuming cost = 7 requires 7, but only 6 available -> Rejection
        result, state = TokenBucketEngine.consume(
            rule, state, cost=7.0, current_timestamp=1000.0
        )
        assert result.allowed is False
        assert result.remaining == 6.0
        # Deficit is 7.0 - 6.0 = 1.0 token. At 2 tokens/s, retry_after = 0.5s
        assert pytest.approx(result.retry_after, rel=1e-4) == 0.5


class TestTokenBucketRefill:
    """Validates mathematical correctness of time-decay refills."""

    def test_continuous_fractional_refill(self) -> None:
        # 10 tokens capacity, 5 tokens per second refill
        rule = RateLimitRule(capacity=10.0, refill_rate=5.0)
        clock = MockClock(1000.0)
        state = BucketState(tokens=0.0, last_refill_timestamp=clock.now)

        # Advance 0.4 seconds -> 0.4 * 5 = 2.0 tokens refilled
        clock.advance(0.4)
        result, state = TokenBucketEngine.consume(
            rule, state, cost=1.0, current_timestamp=clock.now
        )
        assert result.allowed is True
        assert pytest.approx(result.remaining, rel=1e-4) == 1.0
        assert state.last_refill_timestamp == 1000.4

    def test_capacity_ceiling_enforcement(self) -> None:
        rule = RateLimitRule(capacity=10.0, refill_rate=5.0)
        clock = MockClock(1000.0)
        state = BucketState(tokens=5.0, last_refill_timestamp=clock.now)

        # Advance 100 seconds (would generate 500 tokens without ceiling)
        clock.advance(100.0)
        result, state = TokenBucketEngine.consume(
            rule, state, cost=1.0, current_timestamp=clock.now
        )

        assert result.allowed is True
        # Tokens should cap at 10.0, minus 1 consumed = 9.0
        assert pytest.approx(result.remaining, rel=1e-4) == 9.0
        assert pytest.approx(state.tokens, rel=1e-4) == 9.0
        assert state.last_refill_timestamp == 1100.0

    def test_clock_skew_backwards_drift_handled_safely(self) -> None:
        rule = RateLimitRule(capacity=10.0, refill_rate=5.0)
        state = BucketState(tokens=5.0, last_refill_timestamp=1000.0)

        # Simulated backwards clock drift (NTP synchronization skew)
        skewed_timestamp = 995.0  # 5 seconds in the past

        result, state = TokenBucketEngine.consume(
            rule, state, cost=1.0, current_timestamp=skewed_timestamp
        )

        assert result.allowed is True
        # No refill added, tokens decremented from 5 to 4
        assert state.tokens == 4.0
        # Timestamp must not regress
        assert state.last_refill_timestamp == 1000.0

