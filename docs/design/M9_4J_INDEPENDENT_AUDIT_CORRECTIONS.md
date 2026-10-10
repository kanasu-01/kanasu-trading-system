# M9.4j - Independent post-publication audit corrections

## 1. Status

`M95_GATE=BLOCKED`

M9.4j is a corrective work package created after a fresh independent review of
the published M9.4i state found six remaining issues, R01-R06.

M9.4j is not M9.5 design and does not authorize M9.5 implementation.

Repository branch:

`m9-v1-research-platform`

Published baseline at the start of M9.4j:

`0ba32ee2294f7d6a84288574860a7d1f995f1e34`

The M9.4j corrective candidate is published and post-push verified at `7f123daa135be4009294f5197676dc5153261255`, whose parent is `0ba32ee2294f7d6a84288574860a7d1f995f1e34`.

## 2. Preservation boundaries

M9.4j preserves accepted M4 Backtest financial semantics, M5 WFA mathematics,
M6/M7 Paper causality, M8 application authority, M9.2 durable computation and
evidence identities, M9.3 canonical instrument/dataset truth, fixed Trial
denominators, append-only history, bounded workers, Start/Retry separation,
cooperative cancellation/recovery, independent per-instrument simulated
accounts, absence of M9.4 qualification authority and absence of live-order
authority.

No corrective finding authorizes guessed provider, procedure, economic or data
mappings.

## 3. R01 - Complete financial configuration freeze

Severity: HIGH.

Registered execution must freeze the complete effective result-affecting
Backtest financial configuration rather than only caller-declared fragments.

M9.4j resolves omitted canonical values from the authoritative RuntimeContext,
rejects unknown financial keys, persists the complete mapping and requires
claimed execution to prove exact equality with both registered and executable
runtime configuration.

The canonical mapping includes effective risk per trade, slippage percentage,
slippage-enabled state, brokerage-enabled state and the accepted economic-policy
payload. Existing M4 financial authority remains unchanged.

## 4. R02 - RunAttempt lifecycle ownership

Severity: HIGH.

Standalone M9.2 attempts and ResearchJob-owned attempts are separate lifecycle
ownership domains.

Standalone attempt terminalization rejects any attempt referenced by a
ResearchJob inside the same transaction before terminal state, evidence or
artifact mutation. Standalone startup recovery excludes ResearchJob-owned
RUNNING attempts.

ResearchJob recovery and coordinated terminalization remain authoritative for
owned attempts.

A caller-supplied existing RunAttempt passed to `execute_prepared()` requires a
matching terminalizer. Automatic standalone terminalization is only available
for an attempt created by the standalone orchestrator path itself.

## 5. R03 - Reuse requires canonical result validation

Severity: MEDIUM.

A historical result is not reusable merely because metadata, byte count,
accepted evidence and content identity match.

`find_exact_reusable_execution()` now decodes and validates the actual canonical
Backtest-result bytes before reuse. Malformed canonical payloads are skipped.

## 6. R04 - Impossible finite result states fail validation

Severity: MEDIUM.

Canonical result validation now rejects directly represented impossible finite
long-only cash-equity states including invalid positive-price/OHLC structure,
negative volume, negative position size, zero-position cash/equity disagreement,
non-positive execution prices when present, non-positive trade entry or closed
exit prices and negative stop prices.

This is structural/semantic validation only. It does not recompute fills,
brokerage, cash, P&L, equity or other Backtest economics.

## 7. R05 - Trial-detail snapshot consistency

Severity: MEDIUM.

Trial detail previously composed lineage from several independent catalog reads.

M9.4j introduces an immutable `ResearchTrialDetailSnapshot` assembled through
one SQLite connection and one explicit read transaction. Trial, disposition
events, ResearchJobs, owned attempts and reused attempts therefore come from one
consistent committed database snapshot before API projection.

The HTTP response schema remains unchanged.

## 8. R06 - Documentation synchronization

Severity: LOW.

Current-state architecture and project-status documentation must describe the
M9.4j corrections truthfully while historical M9.4g/M9.4h/M9.4i review records
remain unchanged.

This document is the dedicated M9.4j correction record.

## 9. Final whole-package validation evidence

The integrated M9.4j corrective candidate was validated as one package after R01-R06 were present together and was subsequently published at `7f123daa135be4009294f5197676dc5153261255`.

Reproduced evidence:

- changed M9.4j Python production/test files compiled successfully;
- all 21 `test_m94*.py` files: 259 passed;
- broad `pytest tests -k m94 -q`: 265 passed, 1100 deselected;
- explicit preservation set: 23 passed;
- complete `pytest tests -q`: 1365 passed;
- historical M9.4g/M9.4h/M9.4i audit documents remained unchanged;
- `git diff --check`: passed;
- known Windows status-only strategy entries remained content-clean.

The preservation selector found no filename-matched `test_m92*.py` or
`test_m93*.py` files and therefore explicitly exercised the shared Backtest
research orchestrator test file. The complete 1365-test repository regression
is the authoritative cross-milestone preservation result for the integrated
working tree.

These validation results and post-push verification establish the published corrective candidate. They do not constitute independent acceptance or M9.5 authorization.

## 10. Independent-audit requirement at M9.4j publication

Staging, commit, push and post-push local/remote verification are complete for
published corrective HEAD:

`7f123daa135be4009294f5197676dc5153261255`

At M9.4j publication, the remaining M9.4 gate was a fresh independent
audit of that exact published HEAD.

Only:

`M95_GATE=PASS`

authorizes fresh M9.5 design.

A PASS authorizes M9.5 design only; M9.5 implementation remains separately
approved work.

## 11. Post-publication independent audit and M9.4k follow-up

The subsequent independent audit of exact published M9.4j HEAD
`7f123daa135be4009294f5197676dc5153261255` returned:

`M95_GATE=BLOCKED`

The accepted-scope findings were:

- F01 MEDIUM - registered `data_treatment_basis` could be empty or incomplete,
  allowing executable price-adjustment verification to be bypassed;
- F02 MEDIUM - canonical Backtest-result validation admitted direct impossible
  long-only states including non-positive trade/execution quantities, non-LONG
  direction, positive stored drawdown, and positive holdings without positive
  marked position value;
- F03 LOW - current-state documentation/traceability lagged the actual
  post-publication state.

M9.4k is the bounded follow-up correction. It does not redesign M9.4 or alter
accepted M4 financial semantics. The local candidate requires explicit
`price_adjustment` registration using `raw`, `adjusted` or `unknown`; preserves
explicit `unknown` without guessing; fails incomplete registered plans closed;
strengthens only direct canonical long-only invariants; and adds real
registration/execution plus canonical artifact reuse/aggregation
counterexample tests.

Validation of the current local M9.4k candidate includes:

- 107 affected M9.4 tests passing;
- 73 previously failing queue/attempt/cancellation tests passing after three
  stale historical fixtures were corrected from the obsolete `adjustment`
  key to canonical `price_adjustment`;
- complete Python regression: 1375 passed;
- `git diff --check`: PASS.

M9.4k is not yet staged, committed or pushed. M9.5 remains blocked until the
M9.4k corrective candidate is published, the exact local/remote published HEAD
is verified, and a fresh independent audit of that exact HEAD returns exactly:

`M95_GATE=PASS`
