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

### Implementation quality requirements

Every production change must explicitly consider, where relevant:

1. input and state validation at the correct boundary;
2. expected failure behavior and clear error handling;
3. protection against partial or corrupt authoritative state;
4. resource safety, transaction rollback, cleanup, and release of files, connections, and other resources;
5. useful logging and diagnostics at material operational boundaries and failures;
6. observability sufficient to diagnose important failures;
7. configuration of environment- or runtime-specific values instead of inappropriate hard-coding;
8. security and secrets handling, including preventing credential or sensitive-data leakage through logs and errors;
9. concise code-level documentation for non-obvious contracts, invariants, and behavior; and
10. success-path, boundary, expected-failure, and regression tests proportional to the contract and risk.

These are engineering considerations, not mandatory boilerplate. Add only what the task contract and operational risk justify; do not add meaningless logging, exception wrapping, configuration, comments, abstractions, or tests to satisfy a checklist. Record or defer material issues outside the authorized scope rather than implementing them silently.

## 9. Testing and evidence

Testing is required in proportion to the contract and risk. Where applicable, validation covers success, boundaries, expected failures, and regressions. Behavioral tests should establish observable outcomes rather than private implementation details.

Use focused tests during development. Run the required broader suite before closure when authorized and appropriate. Preserve existing tests unless their contract is genuinely wrong; explain a test-contract problem before changing it. Do not weaken tests to obtain a green result.

Test count is evidence about suite size, not project progress, economic validity, profitability or release readiness.

### Lean agent execution policy

Coding-agent reasoning should focus on work that benefits from implementation context: exact-current-file inspection; relevant contract, architecture and validation reading; authorized implementation and refactoring; focused test creation and execution; debugging failures caused by the change; and acceptance-criteria self-checks.

Mechanical repository verification normally belongs to independent review rather than the coding agent. This includes Git status, log, diff, diff-check, stat and numstat; repository line counting; staging, commit and push; remote commit verification; routine documentation closure; and repository-wide mechanical checks that do not help diagnose the implementation.

During implementation, the coding agent normally runs the focused tests needed to develop and debug the authorized change. Broader or full regression validation remains required whenever task validation or closure rules require it, but it may be run independently in the local repository and reviewed before commit or closure. This policy refines who normally runs broader validation; it does not weaken when that validation is required.

The coding agent should run broader or full validation itself when the result materially supports correct implementation, diagnosis or integration. Examples include unclear cross-module impact, failures outside focused scope, shared or foundational infrastructure changes, repeated correction rounds, major integration work, release or validation tasks whose outcome is needed to finish correctly, and an explicit user request or authorization.

The normal responsibility split is:

- **Coding agent:** authorized implementation, focused validation and implementation-time debugging.
- **Independent review:** exact diff and scope review, broader regression validation, Git/repository verification and commit approval.

If broader validation exposes a failure that requires implementation reasoning, return the exact failure evidence to the coding agent, correct the scoped implementation, and rerun the appropriate focused and broader validation.

Resource or credit conservation never overrides required validation or engineering quality. It must not reduce test coverage, suppress failures, weaken tests, replace necessary reasoning or become a blanket rule that the full suite is never run. Validation ownership remains risk- and task-dependent.

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

For routine documentation-only closure, reuse already accepted implementation and test evidence, update only the authoritative documents actually affected, and do not rerun tests merely because documentation is being synchronized. Do not repeat repository-wide discovery or auditing unless an inconsistency or missing evidence requires it.

Before closure:

1. Check documentation impact.
2. Update the owning document.
3. Repair affected links.
4. Update Project Status and roadmap evidence where the milestone state changes.
5. Verify current and target behavior are not conflated.

## 13. Progress measurement

Show progress summaries only at meaningful major closure points: major step or task closure, major sub-milestone closure, milestone closure, version closure, or when explicitly requested. Ordinary development replies do not require a progress summary.

When applicable, report at least current work or step, current milestone, and current version. Near-term progress uses evidence-based lifecycle state or accepted leaf-scope completion. Higher-level milestone or version percentages may be labelled **approximate** when future scope is not completely baselined. Preserve enough of the calculation basis to make a percentage reproducible, avoid speculative precision, and report implementation and validation progress separately where they differ.

Accepted scopes may use 1, 2, 3, 5, 8 or 13 effort points at the leaf-task level. Do not use test count, repository line count, calendar time, or number of headings as the completion percentage itself. Avoid parent/child double counting and rebaseline transparently when accepted scope changes. Do not invent estimates for historical work merely to construct a progress meter.

A progress summary may include supporting engineering metrics such as tests before and after, repository line changes, current commit, and next major work. These support the summary; they are not completion percentages.

### Repository line changes

Call Git line statistics **repository line changes**, rather than treating every changed line as executable lines of code. At a major closure, when useful, separate Production files, Test files, and Documentation files with added, deleted, and net line counts. Comments, imports, blank lines, and docstrings in production files remain production-file line changes. This metric does not measure quality or completion.

## 14. Journaling, reporting and UI

Runtime journals should be session-isolated, append-oriented and inspectable. A storage format is an architectural choice when durability or compatibility makes it material.

Research reporting must prioritize correct account/economic meaning and reproducibility before visual sophistication.

The frontend remains modular, lightweight and workflow-oriented. It presents backend commands and authoritative snapshots; it does not own or recompute trading/account state.
