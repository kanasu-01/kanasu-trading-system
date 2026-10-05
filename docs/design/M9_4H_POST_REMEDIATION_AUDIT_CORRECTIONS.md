# M9.4h - Post-Remediation Independent Audit Corrections

## Status

CORRECTIVE IMPLEMENTATION VALIDATED THROUGH M9.4h3; M9.4h4 RE-CLOSURE CANDIDATE; INDEPENDENT RE-REVIEW PENDING.

M9.5 remains BLOCKED.

This corrective slice exists because the independent post-remediation
audit at M9.4 re-closure HEAD reproduced residual integrity defects after
M9.4g.

This is a bounded correction to M9.4. It is not an M9.5 design and does
not introduce qualification authority.

## 1. Authoritative baseline

Repository:

`kanasu-01/kanasu-trading-system`

Branch:

`m9-v1-research-platform`

Original corrective baseline HEAD:

`c3bcfa148a851d48f61d29f9ee1c4431139cc353`

Published corrective implementation heads:

- `d1efd238c3ee0762de7a31647c3c919f98dbcab6` - N01-N04;
- `524b9dda8ab40ac5da9de44a284310fa163e21e9` - N05-N06.

The independent post-remediation audit returned:

`M95_GATE=BLOCKED`

Blocking findings:

- N01 - mutable inputs can change during final identity verification;
- N02 - registered intent can diverge from executable truth;
- N03 - registered exact reuse can omit successor dataset lineage;
- N04 - authoritative integrity failures can be reduced to ordinary
  failures while later work is still claimed;
- N05 - standalone revision persistence can bypass complete registered
  population authority.

Non-blocking but accepted corrective findings:

- N06 - FIFO ordering is lexical rather than semantic across timezone
  offsets;
- N07 - closure and traceability documentation overstates completion or
  remains inconsistent.

## 2. Purpose

M9.4h shall close only the residual defects independently reproduced
after M9.4g.

It must:

1. bind accepted execution evidence to stable inputs actually consumed;
2. bind registered material intent to the same executable truth;
3. make registered procedure identity authoritatively provable;
4. remove the registered-reuse lineage bypass;
5. propagate authoritative state/integrity failures fail-closed through
   all relevant boundaries;
6. make complete population registration the only startable revision
   authority;
7. make FIFO chronology semantic across valid timezone offsets;
8. synchronize closure documentation only after corrected behavior is
   proven.

## 3. Preservation boundaries

M9.4h must preserve:

1. M4 Backtest timing, fills, sizing, P&L, drawdown and execution
   feedback semantics;
2. M5 walk-forward mathematics;
3. M6/M7 Paper causality;
4. M8 application authority;
5. M9.2 ExperimentSpec, RunAttempt, evidence and immutable artifact
   identities except for stricter integrity enforcement;
6. M9.3 canonical instrument, universe and DatasetIdentityV2 truth;
7. the fixed StudyRevision Trial denominator;
8. independent Trial accounts rather than shared-capital portfolio
   claims;
9. bounded local worker execution;
10. duplicate-safe claims and atomic attempt binding;
11. append-only retry/history semantics;
12. Start separate from Retry;
13. recovery separate from resume/retry;
14. cooperative cancellation;
15. qualification remaining outside M9.4;
16. live-order authority remaining outside V1 research;
17. the prohibition on guessed provider, procedure, economic or data
   mappings.

The correction must not replace the Backtest engine, SQLite catalog or
bounded worker model.

## 4. N01/N02 - Stable execution and registered-intent binding

### D01 - One stable execution truth

Authoritative financial execution must consume a stable execution
binding.

The binding must represent the exact:

- strategy implementation and effective parameters;
- BacktestConfig material values;
- RuntimeContext economic/risk values;
- DatasetContext;
- price-adjustment/data-treatment basis;
- requested range;
- ordered candle content.

Identity validation and financial execution must refer to that same
stable binding.

It is not sufficient to project a manifest from mutable objects, perform
artifact I/O, and later execute the original mutable objects.

No accepted result may describe different inputs from those actually
consumed by the financial engine.

### D02 - Isolation from external mutation

The implementation must isolate authoritative execution from later
mutation of resolver-owned objects.

The implementation may use immutable value snapshots, isolated copies,
or another mechanism that proves the objects consumed by execution
cannot drift after final validation.

A lock that unrelated callers are not required to honor is not
sufficient proof.

Candle order/content must remain identical to the canonical prepared
dataset identity.

### D03 - Registered semantics are checked again at the final binding

Registered Trial validation must not occur only before historical
retrieval/preparation.

After preparation and before fresh execution is authorized, the final
stable execution binding must again be proven compatible with the
registered Trial plan.

This must include:

- timeframe;
- range;
- initial capital;
- timezone;
- strategy parameters;
- effective strategy parameters;
- executable risk/economic semantics;
- DatasetContext semantics;
- price-adjustment/data-treatment semantics;
- repository revision;
- procedure identity.

A mutation during retrieval/preparation must therefore fail before
RunAttempt financial execution is accepted.

### D04 - Procedure identity comes from executable authority

`strategy_procedure_id` supplied by an input resolver is not independent
proof of procedure identity.

Registered execution must derive or verify procedure identity from an
accepted executable-code authority.

Preferred bounded contract:

- expose an explicit research procedure identity from the executable
  strategy implementation or an existing canonical strategy authority;
- bind that identity to the repository revision already pinned by the
  StudyRevision;
- compare it to the registered `strategy_procedure_id`;
- reject registered execution when the executable procedure cannot prove
  the registered identity.

The correction must not invent a mapping merely to make a Trial
executable.

Compatibility for non-registered Backtest/Paper callers must be
preserved.

### D05 - Failure semantics

A registered/executable mismatch remains an invalid/unverifiable
research input outcome where appropriate.

An authoritative persistence or artifact-integrity failure is not an
ordinary Trial invalidity and must follow D09-D11 below.

## 5. N03 - Registered exact-reuse authority

### D06 - Dataset lineage is mandatory

A registered exact-reuse completion must never succeed without both:

- requested successor DatasetReference lineage;
- reused source DatasetReference lineage.

Optional omission is removed from the authoritative registered-reuse
contract.

### D07 - Compatibility proof is authoritative

The normal executor must continue to integrity-check DatasetReference
artifacts and compare applicable canonical
`DatasetIdentityV2.dataset_id` values.

The lower persistence boundary must no longer provide a supported public
route that can terminalize registered reuse while bypassing that proof.

Implementation may narrow/private the raw persistence primitive, require
a verified lineage value produced by the compatibility workflow, or
otherwise ensure only the authoritative reuse workflow can produce a
REUSED registered Trial.

The design must continue to permit distinct trusted acquisition
provenance when canonical dataset identity is identical.

No fake RunAttempt may be created for reuse.

## 6. N04 - Authoritative failure propagation

### D08 - Authoritative errors retain their type

`AuthoritativeResearchStateError` or its accepted successor must survive
all relevant boundaries, including:

- registered plan/input resolution;
- historical retrieval coordination;
- preparation;
- manifest/artifact integrity validation;
- attempt/result publication;
- reconciliation.

Generic exception handlers must not silently convert such failures into
ordinary independent Trial failures.

### D09 - Prepared artifact corruption is authoritative

Missing, unreadable, corrupt or identity-inconsistent authoritative
prepared manifest/evidence required to prove execution truth must
propagate as authoritative state/integrity failure where the system can
no longer safely characterize it as an independent strategy outcome.

### D10 - Worker pool remains fail-closed

When an authoritative state/integrity failure reaches the scheduler, the
current pool run must stop initiating new claims.

Already claimed work remains represented truthfully and is handled by
the existing explicit recovery contract.

Ordinary deterministic/transient/invalid/insufficient Trial outcomes
remain isolated and must not unnecessarily stop unrelated work.

### D11 - Direct negative evidence

Tests must include at least:

- authoritative error from input resolution;
- authoritative error during retrieval;
- prepared manifest missing/corrupt during final execution validation;
- two-job pool proving the second job is not newly claimed after each
  authoritative failure.

## 7. N05 - Complete population authority

### D12 - A persisted revision is not automatically startable

No public persistence operation may create a StudyRevision that Start can
treat as completely registered unless its complete Trial population was
published by the authoritative registration transaction.

### D13 - Explicit registration completeness

The persistence model must contain an authoritative way to distinguish:

- complete registered revision population;
- incomplete/non-operational revision state, if such a state remains
  supported internally.

Start must fail closed unless complete registration is proven.

The proof must be written atomically with the authoritative population
registration.

### D14 - Start validates population authority

`start_study_revision_batch()` must reject a revision whose complete
registered population has not been authoritatively established.

A nonempty StudyRevision plan must never become started with zero Trials
merely because an incremental persistence method was called.

### D15 - Existing denominator semantics remain unchanged

For a correctly registered revision:

- Trial count remains fixed;
- Start creates one deterministic initial ResearchJob per Trial;
- repeat Start remains idempotent;
- Retry never creates a Trial;
- registration remains all-or-nothing.

## 8. N06 - Semantic FIFO chronology

### D16 - FIFO uses chronological instants

Queued job selection must compare timezone-aware creation timestamps by
their actual instant rather than lexical ISO-8601 text.

Stable `job_id` remains the deterministic tie-breaker.

Equivalent or differently offset representations must not reorder real
chronology.

The stored timestamp representation need not be rewritten solely for
this correction if semantic ordering can be obtained safely at query or
persistence time.

## 9. N07 - Documentation and re-closure truth

### D17 - Reopen completion claims

Until N01-N05 are fixed and proven, current M9.4 re-closure assertions
are historical claims challenged by the independent audit.

No new documentation update may imply that the independent audit passed.

### D18 - Traceability synchronization

After implementation and tests are proven:

- update M9.4g/M9.4h closure status;
- reconcile PROJECT_STATUS and ROADMAP;
- reconcile ARCHITECTURE and DECISIONS if behavior contracts changed;
- synchronize INVARIANTS and TRACEABILITY, including the previously
  observed 006/011/012 status mismatch and missing 013 counterpart;
- update VALIDATION_PLAN with exact corrective evidence;
- retain the independent audit outcome and corrective chain rather than
  erasing history.

## 10. Implementation order

Implementation is intentionally dependency ordered.

### M9.4h1 - Stable execution truth

Owns:

- N01;
- N02.

Expected production areas:

- claimed Trial input validation/binding;
- Backtest research orchestration;
- executable strategy procedure identity;
- focused adversarial tests.

### M9.4h2 - Reuse and fail-closed authority

Owns:

- N03;
- N04.

Expected production areas:

- registered exact-reuse workflow;
- SQLite research catalog persistence boundary;
- successor retrieval coordinator;
- claimed job executor;
- worker-pool fail-closed tests.

### M9.4h3 - Population and FIFO authority

Owns:

- N05;
- N06.

Expected production areas:

- StudyRevision registration persistence;
- Start preconditions;
- ResearchJob FIFO claim ordering;
- lifecycle tests.

### M9.4h4 - Re-closure evidence and documentation

Owns:

- N07;
- cross-slice validation.

No documentation may declare corrected closure before h1-h3 behavior is
proven.

## 11. Required validation

Before M9.4 can be re-closed again, evidence must include:

1. direct regression reproductions for N01-N06;
2. focused tests for every changed production boundary;
3. all M9.4-named tests;
4. preservation tests for Backtest, execution, portfolio, risk,
   walk-forward, runtime and Paper behavior;
5. complete Python regression suite;
6. `git diff --check`;
7. exact changed-file review;
8. no unintended staging;
9. clean post-commit and post-push verification after separately
   approved protected operations.

The previously passing 1325-test suite is regression evidence but is not
proof against the new adversarial reproductions.

### Current corrective evidence through M9.4h3

Published behavior corrections:

- N01/N02: stable private execution snapshots, final registered-semantics
  revalidation and executable-code procedure authority;
- N03: mandatory requested/source DatasetReference lineage for registered
  exact reuse;
- N04: authoritative state/integrity failures retain fail-closed semantics
  and stop new worker-pool claims;
- N05: schema-v5 durable complete-population proof written by authoritative
  registration and required by Start;
- N06: FIFO compares exact timezone-aware UTC microsecond instants with stable
  `job_id` tie-breaking.

Validation evidence:

- M9.4h1+h2 focused: 144 passed;
- M9.4h3 focused: 66 passed;
- current-head M9.4-wide: 172 passed;
- current-head expanded cross-milestone preservation: 1342 passed;
- current-head complete Python: 1342 passed;
- `git diff --check`: passed;
- h1+h2 published at `d1efd238`;
- h3 published at `524b9dda`.

N07 documentation synchronization and protected publication/post-push
verification remain part of h4. None of this evidence claims the independent
re-review passed; `M95_GATE` remains `BLOCKED`.

## 12. Re-review gate

After implementation and local re-closure evidence, perform a bounded
independent re-review.

The re-review should primarily:

- reproduce N01-N06;
- verify N07 documentation;
- inspect changed authority boundaries;
- run required focused and broad regressions;
- return exactly one final M9.5 gate decision.

M9.5 may begin design only after:

`M95_GATE=PASS`

A passing re-review authorizes M9.5 design, not automatic M9.5
production implementation.

## 13. Protected publication boundary

M9.4h4 documentation synchronization is not itself permission to mutate Git
history or remote state.

Staging, commit and push remain three separately approved protected operations
under the Kanasu Runner protocol. Final M9.4h re-closure evidence must include
clean post-commit and post-push verification before the independent re-review
is requested.
