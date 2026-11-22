# Project Progress & Engineering Milestones Tracker

This document tracks active development progress, phase milestones, and subphase deliverables for the **Adaptive Distributed Rate Limiter & Quota Engine**.

---

## Master Architecture Roadmap

- [ ] **Phase 1: Baseline Distributed Rate Limiter MVP** *(Active)*
  - Establish a fully functioning, standard distributed rate limiter using FastAPI, Token Bucket algorithm, and Redis backing store. Benchmark baseline latency and identify Redis round-trip bottlenecks.
- [ ] **Phase 2: Atomic Concurrency & Anti-Drift Engine**
  - Author and integrate custom atomic Redis Lua scripts (`EVALSHA`) to consolidate token replenishment, consumption, and expiration in a single round-trip without race conditions.
- [ ] **Phase 3: High-Throughput Token Leasing & gRPC Control Plane**
  - Implement bidirectional gRPC streaming over HTTP/2 between FastAPI edge nodes and a central coordinator; introduce local in-memory token leasing to achieve zero-network hot paths.
- [ ] **Phase 4: Adaptive Congestion Control & Priority Load Shedding**
  - Engineer the Additive Increase, Multiplicative Decrease (AIMD) feedback loop adjusting global quotas based on downstream latency gradients ($p99$) and error rates; implement priority-based request dropping (Tier 1 vs Tier 3).
- [ ] **Phase 5: Resilience, Backpressure & Circuit Breaking**
  - Implement fail-open / fail-closed circuit breakers on edge nodes, self-healing reconnection, and bounded `asyncio.Queue` telemetry backpressure buffers.
- [ ] **Phase 6: Real-Time Observability & Chaos Dashboard**
  - Build a live WebSocket telemetry feed and Next.js/React frontend visualizing dynamic AIMD quota ceilings alongside downstream latency curves with synthetic chaos injection.

---

## Phase 1: Baseline Distributed Rate Limiter MVP

### Subphase Breakdown & Status
- [x] **Subphase 1.1: Core Token Bucket Algorithm & State Model**
  - Status: *Completed (Tests passing, Walkthrough authored)*
  - Deliverables: Pure domain token bucket implementation, time-decay refill calculations, burst handling, strict unit test suite (TDD).
- [ ] **Subphase 1.2: Redis Storage Adapter & State Synchronization**
  - Status: *In Progress (Branch created, specification authored)*
  - Deliverables: Async Redis backend adapter, key expiration TTLs, serialized state persistence, integration tests with Redis mock/server.
- [ ] **Subphase 1.3: FastAPI Middleware & HTTP Rate-Limiting Contract**
  - Status: *Pending*
  - Deliverables: ASGI middleware intercepting requests, client identification (`X-API-Key` / IP), standard headers (`X-RateLimit-*`), `429 Too Many Requests` + `Retry-After`.
- [ ] **Subphase 1.4: Benchmark Harness & Bottleneck Profiling**
  - Status: *Pending*
  - Deliverables: Automated load testing script (Locust/`asyncio`), measuring p50/p95/p99 latency overhead and Redis IOPS bottleneck to establish baseline empirical metrics.

---

## Activity Log

| Date | Subphase | Action Taken | Author/Agent |
| :--- | :--- | :--- | :--- |
| 2026-11-22 | Project Init | Initialized repository governance, `AGENTS.md`, `CLAUDE.md`, uncommitted `SLOs.md`, and progress tracker. | Lead Architect |
| 2026-11-22 | Subphase 1.1 | Implemented TokenBucketEngine domain model and 9 unit tests under TDD; authored walkthrough. | Lead Architect |
| 2026-11-22 | Subphase 1.2 | Created branch feat/subphase-1.2-redis-storage-adapter and authored specification doc. | Lead Architect |
