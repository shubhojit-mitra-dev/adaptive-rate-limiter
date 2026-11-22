# AGENTS.md — Engineering Governance & Operational Rules

> **MANDATORY INSTRUCTION FOR ALL LLM AGENTS:**  
> Every AI agent operating in this repository **must** read, internalize, and strictly obey the rules and protocols in this file before planning, proposing, or executing any command, test, or code change. Zero deviations permitted.

---

## 1. Project Overview & Architecture Vision

This repository hosts the **Adaptive Distributed Rate Limiter & Quota Engine**—a high-throughput, distributed ingress protection system designed with:
- **Data Plane:** FastAPI / Starlette edge gateways running on Granian/uvloop executing zero-network, in-memory token lease checks.
- **Control Plane:** Centralized gRPC workers communicating via bidirectional HTTP/2 streams for telemetry aggregation and AIMD quota redistribution.
- **State Store:** Redis with atomic Lua scripts (`EVALSHA`) for global token accounting.
- **Congestion Control:** Additive Increase, Multiplicative Decrease (AIMD) algorithm throttling limits dynamically against downstream latency gradients ($p99$) and 5xx error rates.

---

## 2. Core Operational Rules for All Agents

### Rule 1: Phase and Subphase Hierarchy
- Development is structured into major sequential **Phases** (e.g., Phase 1: MVP Baseline Rate Limiter, Phase 2: Distributed Concurrency & Lua, Phase 3: In-Memory Token Leasing & gRPC, etc.).
- Each Phase is divided into **3 to 10 granular Subphases** based on technical complexity.
- Subphases must be completed sequentially; jumping ahead or bundling multiple subphases into a single effort is strictly prohibited.

### Rule 2: Git Branching Per Subphase
- Every single subphase **must be developed in its own dedicated Git branch** (e.g., `feat/subphase-1.1-token-bucket-core`).
- Work is merged into `main` strictly through Pull Requests after all tests and walkthrough documentation are verified.

### Rule 3: Strict Test-Driven Development (TDD)
- **Tests come first—no exceptions.**
- For every subphase, before writing any production implementation code:
  1. Author comprehensive test suites covering expected behaviors, edge cases, boundary conditions, and failure scenarios.
  2. Implement necessary mock data, fixtures, and state emulators.
  3. Run the test suite and verify that tests fail expectedly for the right reasons (Red phase of Red-Green-Refactor).
  4. Only then implement the minimum code required to satisfy the tests.

### Rule 4: Phase-Level Documentation
- Before starting any subphase in a new phase, the agent must write a complete Phase Document in `docs/phases/<phase-name>/overview.md`.
- This document must detail:
  - The architectural goal of the phase.
  - Concrete deliverables.
  - Verification benchmarks.
  - Expected system behavior and contracts upon phase completion.

### Rule 5: Just-In-Time Subphase Documentation
- The agent must create **only one subphase documentation at a time** (e.g., `docs/phases/phase-1/subphase-1.1.md`).
- Do **not** pre-generate all subphase docs upfront. Each subphase specification must be authored just before beginning that specific subphase.
- All architectural decisions, design trade-offs, and ADRs must be formally documented as Markdown files under `docs/adrs/` or `docs/architecture/`.

### Rule 6: Running Progress & Milestones Tracker
- Maintain an active, running progress log and milestone checklist in `docs/progress.md`.
- Update this file continuously after each milestone, subphase transition, or architectural milestone completion.

### Rule 7: Strict Atomic Commit Strategy
- **Every small change must be committed immediately.**
- **Committing more than one file per commit is strictly forbidden.**
- Each commit must contain **exactly one modified or added file**, accompanied by a clear, semantic commit message (e.g., `feat: implement token bucket consumption logic`, `test: add edge-case unit test for burst limit`).

### Rule 8: Rigorous Error Tracing & Root-Cause Diagnosis
- If an error, exception, or failure occurs during development or test execution:
  - Do **not** guess or blindly patch symptoms.
  - Trace the error thoroughly: identify the exact file, module, function, and line number.
  - Explain what the error is, why it was thrown, and diagnose the underlying root cause before applying a targeted fix.

### Rule 9: Subphase PR & Detailed Code Walkthrough
- Upon completing all deliverables and passing all tests in a subphase:
  - Open a Pull Request on GitHub.
  - Create a dedicated walkthrough file: `docs/walkthroughs/walkthrough-<subphase>.md`.
  - The walkthrough must include:
    1. A concise executive summary of what was accomplished.
    2. A complete file-by-file summary of all changes and git diffs in the branch.
    3. A **Guided Reading Order**: explicitly instruct the reviewer which file and function to read first, second, and so on, to systematically comprehend the architectural flow.
    4. Code excerpts accompanied by deep engineering explanations. Do not provide line-by-line trivial narration; focus on high-level systems mechanics, concurrency patterns, async event-loop subtleties, or performance designs that standard Python developers would not intuitively grasp.

### Rule 10: Sequential Advancement Post-Merge
- Proceed to the next subphase or phase **only after** the current subphase PR is merged.
- Maintain professional, senior-level production quality at all times so that every component is robust on the first iteration.

### Rule 11: Iterative Feedback Loop
- If the required behavior, performance target, or test criteria are not achieved:
  - Engage in an iterative loop: **Code $\rightarrow$ Test $\rightarrow$ Inspect $\rightarrow$ Refine**.
  - Continue iterating until the system rigorously meets all specifications.

### Rule 12: Architecture & Coding Principles
- **SOLID Principles:** Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion.
- **Low-Level Design (LLD):** Clean class contracts, strategy patterns, factory abstractions, and clear separation of concerns.
- **Pythonic Idioms:** Strict type annotations (`typing`), modern async concurrency (`asyncio`), context managers, immutability where appropriate, and memory efficiency.

### Rule 13: Integrity of Test Cases
- If a test case continuously fails, **inspect the implementation**.
- **Never modify or weaken a test case to force a pass** unless an error or incorrect assumption in the test case itself is empirically proven and justified.

### Rule 14: Skill Utilization & Dynamic Installation
- Whenever external skills are required to enhance agent capabilities, install them **globally** (never inside the local project repository) using:
  ```bash
  npx skills add <owner/repo>
  ```

### Rule 15: Skill Discovery Protocol
- To discover and select the most relevant skill for any specialized capability, run:
  ```bash
  npx skills use "https://github.com/vercel-labs/skills" --skill "find-skills"
  ```
  Follow the generated skill instructions, redirect output to a temporary file if necessary, and resolve all relative paths from its supporting directory. Remember: all skills must be installed globally, not in the project directory.

### Rule 16: Production-Grade Quality, Security & Optimization
- Prioritize:
  - **Security:** Strict input sanitization, header verification, prevention of timing attacks and resource exhaustion.
  - **Concurrency Safety:** Race-condition prevention, atomicity guarantees, lock contention elimination.
  - **Performance Optimization:** Hot-path zero-allocation, minimal async context switching, avoidance of unnecessary serialization.
  - **Maintainability:** Modular, extensible codebase engineered for long-term scalability.
