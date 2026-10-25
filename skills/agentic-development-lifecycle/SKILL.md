---
name: agentic-development-lifecycle
description: Mandatory local ADLC adapter for substantive software, AI agent, SaaS, cloud, integration, infrastructure, CI/CD and maintenance work in this repository.
version: 1.0.0
reviewed: 2026-10-25
canonical_owner: vmoulakakis/Myagenticteam
---

# Agentic Development Lifecycle — local project adapter

Authoritative source (pinned to verified merged revision):
https://github.com/vmoulakakis/Myagenticteam/blob/6fab79d7e7b3f5024b5f95d048f5a5235345bc9c/skills/agentic-development-lifecycle/SKILL.md

This adapter is self-contained for coding-agent discovery. A remote GitHub link is a reference, not an automatic skill installation.

## Execute the lifecycle
1. **Intent:** inspect real repo/system and capture the problem, baseline, source, exclusions, risks and measurable acceptance criteria.
2. **Specify:** document architecture, APIs/data and auth contracts, trust boundaries, failures, telemetry, costs, alternatives and rollback.
3. **Plan:** specify scoped steps, dependencies, accountable owner, execution limits, testing/eval coverage and exact approval requirements.
4. **Build:** implement only in this app's repository; use deterministic tooling before agents, smallest necessary permissions, bounded tool/model work and reviewable commits.
5. **Test:** run actual relevant tests/typechecks, integration/E2E, security/privacy/regression checks, and replayable AI evals where agent behavior changes. Capture run IDs and honest failures.
6. **Review:** inspect the diff and evidence. High-impact or irreversible production actions require independent review and explicit human approval bound to the exact action and revision.
7. **Deploy:** verify CI/build, stage, rollout strategy and rollback; never infer production health from Git commit, build, or a model response.
8. **Maintain:** record actual critical-path probes, telemetry, alerts, cost and incidents. Production signals open a new intent; they cannot self-approve a fix.

For material changes create `.adlc/CHG-ID/intent.md`, `spec.md`, `plan.md`, `review.md`, `production-signal.md` sharing a change_id, or equivalent linked issue/PR/release artifacts. Link evidence: issue, commit, CI, eval, approvals, deploy and monitoring. No private chain-of-thought, passwords or PII in tracked artifacts.

Choose proportional risk: light (docs-only), standard (features/fixes), high (payments, auth, privacy, privileged writes, destructive migrations and autonomous external effects). For high risk require rollback and specific approval. Missing runtime evidence means UNVERIFIED, not GREEN.

## Priority
Existing application-specific `AGENTS.md`, `DESIGN.md`, security contracts, SAP production read-only policies, permissions, RLS, restrictions and established CI tests remain mandatory. ADLC adds traceability and gates; it never grants authorization, changes deployment targets, or replaces the canonical `agent-runtime-2026` execution skill. If central skill is inaccessible, follow the safe local lifecycle, document the gap and block unsafe changes.
