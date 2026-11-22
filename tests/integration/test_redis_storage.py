"""
Integration tests for the Redis storage adapter.

Tests state serialization, key TTL setting, multi-tenant isolation,
rejection semantics, and integration with the TokenBucketEngine.
"""

import pytest
import fakeredis.aioredis
from rate_limiter.domain.token_bucket import RateLimitRule, BucketState
from rate_limiter.infrastructure.redis import RedisStorageBackend


@pytest.fixture
async def fake_redis():
    """Provides an isolated in-memory async Redis instance."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.flushall()
    await client.aclose()


@pytest.fixture
async def storage(fake_redis):
    """Provides a RedisStorageBackend backed by fake_redis."""
    return RedisStorageBackend(client=fake_redis, key_prefix="test_rl")


class TestRedisStorageBackend:
    """Integration test suite for Redis state persistence and rate limit evaluation."""

    async def test_initial_request_initializes_state(self, storage: RedisStorageBackend, fake_redis) -> None:
        rule = RateLimitRule(capacity=10.0, refill_rate=2.0)
        now = 1700000000.0

        # Key does not exist initially
        state_before = await storage.get_state("user_1")
        assert state_before is None

        # First evaluation should initialize to capacity, consume 1, and persist 9
        result = await storage.evaluate(
            key="user_1",
            rule=rule,
            cost=1.0,
            current_timestamp=now,
        )

        assert result.allowed is True
        assert result.limit == 10.0
        assert result.remaining == 9.0
        assert result.retry_after is None

        # Verify Redis state directly
        state_after = await storage.get_state("user_1")
        assert state_after is not None
        assert state_after.tokens == 9.0
        assert state_after.last_refill_timestamp == now

        # Verify TTL was set on the key
        ttl = await fake_redis.ttl("test_rl:user_1")
        assert ttl > 0

    async def test_sequential_requests_decrement_quota(self, storage: RedisStorageBackend) -> None:
        rule = RateLimitRule(capacity=5.0, refill_rate=1.0)
        now = 1700000000.0

        # Consume 3 tokens sequentially at same timestamp
        for i in range(1, 4):
            result = await storage.evaluate(
                key="user_seq",
                rule=rule,
                cost=1.0,
                current_timestamp=now,
            )
            assert result.allowed is True
            assert result.remaining == 5.0 - i

        state = await storage.get_state("user_seq")
        assert state is not None
        assert state.tokens == 2.0

    async def test_exhaustion_denies_request_without_corrupting_state(self, storage: RedisStorageBackend) -> None:
        rule = RateLimitRule(capacity=2.0, refill_rate=1.0)
        now = 1700000000.0

        # Consume 2 tokens (capacity reached)
        await storage.evaluate(key="user_exhaust", rule=rule, cost=1.0, current_timestamp=now)
        await storage.evaluate(key="user_exhaust", rule=rule, cost=1.0, current_timestamp=now)

        # 3rd request must be denied
        result = await storage.evaluate(key="user_exhaust", rule=rule, cost=1.0, current_timestamp=now)
        assert result.allowed is False
        assert result.remaining == 0.0
        assert result.retry_after is not None
        assert pytest.approx(result.retry_after, rel=1e-4) == 1.0

        # Verify state in Redis is still 0.0, not negative
        state = await storage.get_state("user_exhaust")
        assert state is not None
        assert state.tokens == 0.0

    async def test_time_decay_refill_persists_to_redis(self, storage: RedisStorageBackend) -> None:
        rule = RateLimitRule(capacity=10.0, refill_rate=5.0)
        t0 = 1700000000.0

        # Empty the bucket at t0
        await storage.evaluate(key="user_refill", rule=rule, cost=10.0, current_timestamp=t0)
        state_t0 = await storage.get_state("user_refill")
        assert state_t0 is not None
        assert state_t0.tokens == 0.0

        # Advance 1.0 second -> 5 tokens replenished. Consume 2 -> leaves 3
        t1 = t0 + 1.0
        result = await storage.evaluate(key="user_refill", rule=rule, cost=2.0, current_timestamp=t1)
        assert result.allowed is True
        assert pytest.approx(result.remaining, rel=1e-4) == 3.0

        state_t1 = await storage.get_state("user_refill")
        assert state_t1 is not None
        assert pytest.approx(state_t1.tokens, rel=1e-4) == 3.0
        assert state_t1.last_refill_timestamp == t1

    async def test_multi_tenant_isolation(self, storage: RedisStorageBackend) -> None:
        rule = RateLimitRule(capacity=5.0, refill_rate=1.0)
        now = 1700000000.0

        # Exhaust tenant A
        for _ in range(5):
            await storage.evaluate(key="tenant_A", rule=rule, cost=1.0, current_timestamp=now)

        denied_result_a = await storage.evaluate(key="tenant_A", rule=rule, cost=1.0, current_timestamp=now)
        assert denied_result_a.allowed is False

        # Tenant B should still have full capacity
        allowed_result_b = await storage.evaluate(key="tenant_B", rule=rule, cost=1.0, current_timestamp=now)
        assert allowed_result_b.allowed is True
        assert allowed_result_b.remaining == 4.0
