# Adaptive Distributed Rate Limiter & Quota Engine

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Data_Plane-009688.svg)](https://fastapi.tiangolo.com/)
[![Redis](https://img.shields.io/badge/Redis-State_Store-DC382D.svg)](https://redis.io/)
[![gRPC](https://img.shields.io/badge/gRPC-Control_Plane-244c5a.svg)](https://grpc.io/)
[![Architecture](https://img.shields.io/badge/Architecture-Decoupled_Data%2FControl_Plane-orange.svg)]()

A high-throughput, distributed ingress protection and dynamic quota engine. Unlike traditional static rate limiters (e.g., fixed "100 req/min"), this system continuously monitors downstream service health, latency gradients, and 5xx error spikes, dynamically throttling traffic in real time using an **Additive Increase, Multiplicative Decrease (AIMD)** congestion control algorithm.

---

## High-Level Architecture Overview

```
                      [ Incoming HTTP Traffic ]
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │   FastAPI Edge Node   │◄───┐
                     │     (Data Plane)      │    │
                     └──────────┬────────────┘    │
                                │                 │
          Zero-Network In-Memory│                 │ Bi-directional
          Token Lease Checks    │                 │ gRPC Streams
          (<0.35ms p99)         │                 │ (10ms Batches)
                                ▼                 │
                     ┌───────────────────────┐    │
                     │   Downstream API      │    │
                     │   Protected Service   │    │
                     └──────────┬────────────┘    │
                                │                 │
                       RTT / Error Telemetry      │
                                │                 │
                                ▼                 ▼
                     ┌──────────────────────────────┐
                     │    gRPC Central Coordinator   │
                     │        (Control Plane)       │
                     └──────────────┬───────────────┘
                                    │
                                    ▼
                     ┌──────────────────────────────┐
                     │         Redis Store          │
                     │  (Atomic Lua EVALSHA State)  │
                     └──────────────────────────────┘
```

### The Three Planes
1. **The Data Plane (FastAPI Edge Gateways):** Executes local, in-memory token lease checks with microsecond overhead, bypassing synchronous database hops on the hot path.
2. **The Control Plane (gRPC Coordinator):** Aggregates distributed telemetry across edge nodes, calculates dynamic AIMD quota adjustments, and pushes refreshed allocations down persistent HTTP/2 streams.
3. **The State Store (Redis):** Durable backing store executing atomic Lua scripts for global token accounting, refills, and lease allocations without race conditions.

---

## Project Structure & Documentation

* **[`AGENTS.md`](AGENTS.md):** Mandatory governance rules, engineering protocols, and TDD directives for all automated coding agents.
* **[`CLAUDE.md`](CLAUDE.md):** Agent redirect pointer to `AGENTS.md`.
* **[`docs/progress.md`](docs/progress.md):** Master milestone tracker and subphase progress log.
* **[`docs/phases/`](docs/phases/):** Phase-by-phase architectural specifications and deliverables.
  * [`phase-1/overview.md`](docs/phases/phase-1/overview.md): Phase 1 baseline distributed rate limiter design.
  * [`phase-1/subphase-1.1.md`](docs/phases/phase-1/subphase-1.1.md): Core Token Bucket algorithm specification.

---

## Development Setup

This project uses [`uv`](https://docs.astral.sh/uv/) for Python project and virtual environment management.

### Prerequisites
- Python 3.12+
- `uv` installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Docker & Redis (for distributed integration testing)

### Getting Started
```bash
# Clone the repository
git clone https://github.com/shubhojit-mitra-dev/adaptive-rate-limiter.git
cd adaptive-rate-limiter

# Install dependencies into virtual environment
uv sync

# Run the test suite
uv run pytest
```

---

## Engineering Guidelines
All development follows strict **Test-Driven Development (TDD)**, **SOLID principles**, and **atomic single-file Git commits**. Refer to [`AGENTS.md`](AGENTS.md) for detailed operational protocols.

