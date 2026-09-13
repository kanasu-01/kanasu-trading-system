# Kanasu Governance

## 1. Purpose

This document owns engineering workflow, scope discipline, permanent identifiers, status vocabulary, documentation ownership and synchronization. It does not own product vision, current project status, architecture or roadmap content.

Kanasu should evolve through small, reviewable changes with explicit contracts and evidence. Modularity and simplicity are constraints on design, not reasons to leave correctness unverified.

## 2. Document ownership

| Document | Authoritative responsibility |
|---|---|
| [README](../../README.md) | Human overview and documentation navigation. |
| [AGENTS](../../AGENTS.md) | Concise Codex/AI-agent instructions. |
| [Product Vision](../PRODUCT_VISION.md) | Product purpose, V1/V2 boundaries and long-term horizons. |
| [Project Status](../PROJECT_STATUS.md) | Current baseline, active work, blockers and latest verification. |
| [Architecture](../architecture/ARCHITECTURE.md) | Current/target architecture and known divergences. |
| [Decisions](../architecture/DECISIONS.md) | Architecture decision ledger. |
| [Roadmap](../roadmap/ROADMAP.md) | Permanent delivery hierarchy, sequencing and roadmap status. |
| [Deferred Work](../roadmap/DEFERRED_WORK.md) | Known unresolved technical issues. |
| [AI Research Backlog](../roadmap/AI_RESEARCH_BACKLOG.md) | AI hypotheses and experimental backlog. |
| [Validation Plan](../validation/VALIDATION_PLAN.md) | Definitions of Done, evidence requirements and release gates. |
| [Paper Runtime](../design/PAPER_RUNTIME.md) | Current and target paper-runtime design. |
| [Legacy Snapshot](../archive/LEGACY_PROJECT_SNAPSHOT.md) | Historical and superseded material. |
| [Frontend README](../../frontend/README.md) | Frontend setup and integration status. |

One fact has one authoritative owner. Other documents link to that owner rather than maintaining independent copies.

## 3. Source-of-truth rules

- Current software behavior is established by current code, relevant tests and execution evidence.
- Accepted architecture decisions define intended durable constraints.
- The roadmap defines planned delivery and dependencies.
- Project Status records dated current work and evidence.
- Validation evidence establishes what has been tested; it does not establish untested integration or release readiness.
- Deferred Work records knowingly unresolved issues.
- Historical material provides provenance and is not current guidance.

When sources conflict, record the contradiction and update the owning document. Do not reinterpret stale prose as authority over current code or as authorization for a change.

## 4. Permanent hierarchy and identifiers

The delivery hierarchy is:

~~~text
Version → Phase → Milestone → Step → Task
~~~

Ancestry is metadata, not part of an identifier.

Rules:

1. Never renumber existing M0–M3 identifiers, existing DW identifiers, or AI-001 through AI-010.
2. Never reuse an identifier after cancellation or supersession.
3. A version or phase change updates metadata, not the permanent identifier.
4. Preserve split, merge and supersession links.
5. Do not convert old table serials, Phase 8 or 10.9B/C/D labels mechanically into M-series IDs.
6. Reserve an identifier explicitly before using it for a proposed future milestone.
7. Keep roadmap, deferred-work, AI-research and architecture-decision namespaces distinct.
8. Small checklist actions may remain unnumbered under a permanent task.

## 5. Status dimensions

### Lifecycle

- PLANNED
- READY
- IN_PROGRESS
- BLOCKED
- DEFERRED
- DONE
- CANCELLED
- SUPERSEDED

### Implementation

- NOT_STARTED
- IN_PROGRESS
- IMPLEMENTED

### Validation

- NOT_STARTED
- RED
- PARTIAL
- PASSED

These dimensions are independent. A component may be implemented but not integrated, integrated but insufficiently validated, or validated within a narrow contract without being release-ready. Release readiness requires every mandatory gate; it is not an average of status fields.

## 6. Task-start workflow

~~~text
authorized task
    ↓
Project Status and Roadmap identity
    ↓
relevant Architecture and Decisions
    ↓
applicable Validation Plan
    ↓
exact current implementation files
    ↓
bounded implementation plan
~~~

Before a code change:

1. Confirm the authorized scope and permanent task ID.
2. Inspect the exact current files and relevant tests.
3. Identify contract, architecture and compatibility impact.
4. Record or surface material contradictions and blockers.
5. Prefer a focused RED test for a new behavioral contract.
6. Implement the smallest coherent GREEN change.
7. Avoid unrelated refactors, dependency additions and runtime changes.

Routine work already clearly authorized within the task does not require repeated confirmation. Destructive operations, live/broker actions, external publication or communication, Git staging/commit/push, and material scope expansion require explicit authorization.

## 7. Task-close workflow

~~~text
implementation
    ↓
tests and evidence
    ↓
documentation-impact check
    ↓
update affected authoritative documents
    ↓
Project Status
    ↓
task DONE
~~~

A task becomes DONE only when:

- its scoped implementation or RED-test deliverable is complete;
- required focused and broader validation has acceptable results;
- failures and limitations are reported accurately;
- required documentation synchronization is complete;
- permanent identifiers and evidence links are preserved; and
- no unauthorized Git or external action occurred.

The next task may become READY after review. It does not become authorized or IN_PROGRESS automatically.

## 8. Engineering rules

- Inspect current code before proposing a modification.
- Prefer incremental, reversible changes and complete small workflows.
- Keep strategy, broker, execution, portfolio, reporting, UI, replay and data responsibilities separated.
- Avoid uncontrolled refactors and god classes.
- Refactor when a concrete correctness, duplication, maintainability, testability or workflow problem justifies it.
- Prefer simple mechanisms and low cognitive overhead.
- Do not add distributed systems, frameworks or abstractions without a current need.
- Reuse validated behavior across runtimes while keeping runtime orchestration logically separated.
- Keep hard risk controls deterministic.
- Treat replay as a consumer of recorded candles/signals/trades/journals rather than an alternate owner of strategy state.

## 9. Testing and evidence

Testing is required in proportion to the contract and risk. Behavioral tests should establish observable outcomes rather than private implementation details.

Use focused tests during development. Run the required broader suite before closure when authorized and appropriate. Preserve existing tests unless their contract is genuinely wrong; explain a test-contract problem before changing it. Do not weaken tests to obtain a green result.

Test count is evidence about suite size, not project progress, economic validity, profitability or release readiness.

## 10. Architecture-decision triggers

Create or update an AD when a change affects:

- authoritative ownership of state;
- a cross-module domain or runtime contract;
- persistence identity or schema policy;
- execution/accounting semantics;
- timestamp or normalization policy;
- source selection and side effects;
- security or operational-safety boundaries; or
- a durable alternative whose consequences should remain visible.

Retrospective decisions must be labelled retrospective. Accepted decisions can be superseded but not erased.

## 11. Deferred-work rules

Record a material issue when it is understood but intentionally outside the active task. Include its scope, current behavior, consequence, reason for deferral, target/revisit trigger, dependencies and resolution evidence.

Group findings by root cause where sensible. Do not use the ledger as a generic idea list, and do not silently mark an issue resolved because one part was improved.

## 12. Documentation synchronization

Synchronize documentation when a change affects a public contract, architecture boundary, accepted decision, roadmap/status, material known limitation, validation gate, setup command or user workflow.

Update only the authoritative documents affected by the change. Avoid copying the same status or contract into every file. Small internal changes need not trigger wholesale documentation rewrites.

Before closure:

1. Check documentation impact.
2. Update the owning document.
3. Repair affected links.
4. Update Project Status and roadmap evidence where the milestone state changes.
5. Verify current and target behavior are not conflated.

## 13. Progress measurement

Do not publish unsupported whole-project completion percentages. Future accepted scopes may use 1, 2, 3, 5, 8 or 13 effort points at the leaf-task level and report implementation and validation progress separately.

Do not use lines of code, test count, calendar time or number of headings as completion percentages. Do not invent estimates for historical work merely to construct a progress meter. Record scope rebaselines and avoid parent/child double counting.

## 14. Journaling, reporting and UI

Runtime journals should be session-isolated, append-oriented and inspectable. A storage format is an architectural choice when durability or compatibility makes it material.

Research reporting must prioritize correct account/economic meaning and reproducibility before visual sophistication.

The frontend remains modular, lightweight and workflow-oriented. It presents backend commands and authoritative snapshots; it does not own or recompute trading/account state.
