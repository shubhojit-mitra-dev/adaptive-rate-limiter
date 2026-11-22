"""
Pure domain model and algorithmic engine for the Token Bucket rate limiter.

Follows Clean Architecture principles: zero framework dependencies, zero network I/O,
and deterministic calculations based on time-decay differential equations.
"""

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True, slots=True)
class RateLimitRule:
    """Defines the burst capacity and continuous refill rate for a rate-limited entity."""

    capacity: float
    refill_rate: float

    def __post_init__(self) -> None:
        if self.capacity <= 0.0:
            raise ValueError(f"Capacity must be strictly positive, got {self.capacity}")
        if self.refill_rate <= 0.0:
            raise ValueError(f"Refill rate must be strictly positive, got {self.refill_rate}")


@dataclass(frozen=True, slots=True)
class BucketState:
    """Immutable snapshot of a token bucket's current state."""

    tokens: float
    last_refill_timestamp: float


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    """Outcome of an evaluation request against a rate-limiting rule."""

    allowed: bool
    limit: float
    remaining: float
    reset_after: float
    retry_after: Optional[float] = None


class TokenBucketEngine:
    """Pure functional token bucket state transition engine."""

    @staticmethod
    def consume(
        rule: RateLimitRule,
        state: BucketState,
        cost: float,
        current_timestamp: float,
    ) -> Tuple[RateLimitResult, BucketState]:
        """
        Evaluate and consume tokens from the bucket based on elapsed time.

        Args:
            rule: Static rate-limiting parameters (burst capacity and refill rate).
            state: Current state of the bucket (available tokens and last timestamp).
            cost: Number of tokens requested by the incoming operation.
            current_timestamp: Current unix epoch timestamp in seconds.

        Returns:
            Tuple of (RateLimitResult, new BucketState).

        Raises:
            ValueError: If cost is negative.
        """
        if cost < 0.0:
            raise ValueError(f"Cost cannot be negative, got {cost}")

        # Elapsed time calculation with protection against backwards clock drift (NTP skew)
        elapsed = max(0.0, current_timestamp - state.last_refill_timestamp)

        # Replenish tokens proportional to elapsed time, bounded by capacity
        replenished = elapsed * rule.refill_rate
        available_tokens = min(rule.capacity, state.tokens + replenished)

        # In case clock drifted backwards, do not regress the last refill timestamp
        effective_timestamp = max(state.last_refill_timestamp, current_timestamp)

        if available_tokens >= cost:
            new_tokens = available_tokens - cost
            reset_after = max(0.0, (rule.capacity - new_tokens) / rule.refill_rate)
            result = RateLimitResult(
                allowed=True,
                limit=rule.capacity,
                remaining=new_tokens,
                reset_after=reset_after,
                retry_after=None,
            )
            new_state = BucketState(tokens=new_tokens, last_refill_timestamp=effective_timestamp)
            return result, new_state
        else:
            # Rejection: Deny request without deducting tokens
            deficit = cost - available_tokens
            retry_after = deficit / rule.refill_rate
            reset_after = max(0.0, (rule.capacity - available_tokens) / rule.refill_rate)
            result = RateLimitResult(
                allowed=False,
                limit=rule.capacity,
                remaining=available_tokens,
                reset_after=reset_after,
                retry_after=retry_after,
            )
            new_state = BucketState(tokens=available_tokens, last_refill_timestamp=effective_timestamp)
            return result, new_state

