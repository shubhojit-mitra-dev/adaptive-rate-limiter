"""
Redis storage adapter for distributed rate limiting.

Implements the RateLimitStorageBackend protocol using Redis as an asynchronous
persistent store. Handles key TTL expiration to prevent memory leakage from
inactive tenants.
"""

import math
import time
from typing import Optional, Protocol, Union
import redis.asyncio as aioredis

from rate_limiter.domain.token_bucket import (
    RateLimitRule,
    BucketState,
    RateLimitResult,
    TokenBucketEngine,
)


class RateLimitStorageBackend(Protocol):
    """Abstract protocol for rate-limiting persistence backends."""

    async def get_state(self, key: str) -> Optional[BucketState]:
        """Retrieve the persisted BucketState for an entity, or None if uninitialized."""
        ...

    async def set_state(self, key: str, state: BucketState, ttl_seconds: int) -> None:
        """Persist BucketState with an expiration TTL."""
        ...

    async def evaluate(
        self,
        key: str,
        rule: RateLimitRule,
        cost: float = 1.0,
        current_timestamp: Optional[float] = None,
    ) -> RateLimitResult:
        """Evaluate and deduct tokens for an incoming request against the persisted state."""
        ...


class RedisStorageBackend:
    """Asynchronous Redis storage adapter for rate-limiting bucket state."""

    __slots__ = ("_client", "_redis_url", "_key_prefix", "_owns_client")

    def __init__(
        self,
        client: Optional[aioredis.Redis] = None,
        redis_url: str = "redis://localhost:6379/0",
        key_prefix: str = "rate_limit",
    ) -> None:
        """
        Initialize the Redis storage adapter.

        Args:
            client: Optional pre-configured async Redis client (useful for mocks/tests).
            redis_url: URL used to initialize Redis client if client is not provided.
            key_prefix: Namespace prefix applied to all Redis keys.
        """
        self._redis_url = redis_url
        self._key_prefix = key_prefix
        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            self._client = aioredis.from_url(redis_url, decode_responses=True)
            self._owns_client = True

    def _make_key(self, key: str) -> str:
        """Generate namespaced Redis key."""
        return f"{self._key_prefix}:{key}"

    @staticmethod
    def calculate_ttl(rule: RateLimitRule) -> int:
        """
        Calculate TTL in seconds to retain rate limit state in Redis.

        Ensures inactive keys are evicted from memory after 2x the time needed
        to fully replenish to capacity, with a minimum floor of 60 seconds.
        """
        time_to_fill = rule.capacity / rule.refill_rate
        return max(60, math.ceil(time_to_fill * 2))

    @staticmethod
    def _coerce_float(val: Union[str, bytes, float]) -> float:
        """Safely coerce Redis string/bytes to float."""
        if isinstance(val, (bytes, bytearray)):
            return float(val.decode("utf-8"))
        return float(val)

    async def get_state(self, key: str) -> Optional[BucketState]:
        """
        Fetch bucket state from Redis.

        Returns:
            BucketState instance if key exists and has valid fields, otherwise None.
        """
        redis_key = self._make_key(key)
        data = await self._client.hgetall(redis_key)
        if not data:
            return None

        # Handle both string keys and bytes keys
        tokens_val = data.get("tokens") or data.get(b"tokens")
        refill_val = data.get("last_refill") or data.get(b"last_refill")

        if tokens_val is None or refill_val is None:
            return None

        return BucketState(
            tokens=self._coerce_float(tokens_val),
            last_refill_timestamp=self._coerce_float(refill_val),
        )

    async def set_state(self, key: str, state: BucketState, ttl_seconds: int) -> None:
        """
        Persist bucket state to Redis as a Hash with an expiration TTL.

        Uses pipeline to ensure HSET and EXPIRE are dispatched in a single batch.
        """
        redis_key = self._make_key(key)
        mapping = {
            "tokens": str(state.tokens),
            "last_refill": str(state.last_refill_timestamp),
        }
        async with self._client.pipeline(transaction=True) as pipe:
            pipe.hset(redis_key, mapping=mapping)
            pipe.expire(redis_key, ttl_seconds)
            await pipe.execute()

    async def evaluate(
        self,
        key: str,
        rule: RateLimitRule,
        cost: float = 1.0,
        current_timestamp: Optional[float] = None,
    ) -> RateLimitResult:
        """
        Evaluate and consume tokens for an entity.

        If the key does not exist, initializes state at full capacity.
        Computes elapsed time refill and persists the resulting state.
        """
        now = time.time() if current_timestamp is None else current_timestamp
        existing_state = await self.get_state(key)

        if existing_state is None:
            # Brand new key: starts at maximum capacity at time = now
            state = BucketState(tokens=rule.capacity, last_refill_timestamp=now)
        else:
            state = existing_state

        result, new_state = TokenBucketEngine.consume(
            rule=rule,
            state=state,
            cost=cost,
            current_timestamp=now,
        )

        ttl = self.calculate_ttl(rule)
        await self.set_state(key=key, state=new_state, ttl_seconds=ttl)
        return result

    async def aclose(self) -> None:
        """Close Redis connection pool if owned by this adapter."""
        if self._owns_client and self._client is not None:
            await self._client.aclose()

    async def __aenter__(self) -> "RedisStorageBackend":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.aclose()
