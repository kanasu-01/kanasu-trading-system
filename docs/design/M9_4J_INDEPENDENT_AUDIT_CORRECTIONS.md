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

## 11. Post-publication independent audit and later corrective chain

The independent audit of exact published M9.4j HEAD
`7f123daa135be4009294f5197676dc5153261255` returned
`M95_GATE=BLOCKED` with F01-F03. M9.4k was the bounded follow-up:
explicit `raw` / `adjusted` / `unknown` price-adjustment registration,
fail-closed incomplete registered plans, stricter direct long-only canonical
result invariants, real registration/execution and canonical artifact
reuse/aggregation counterexamples, and synchronized then-current documentation.

Historical M9.4k local validation included 107 affected M9.4 tests, 73 tests
covering corrected stale historical fixtures, all 1375 Python tests and clean
`git diff --check`. The candidate was subsequently separately reviewed, staged,
committed and pushed at
`9ac407fd4910edf9392445a6fa0539ba90fa97c5`; post-push verification confirmed
exact local/remote HEAD equality.

A fresh independent audit of exact published M9.4k HEAD then returned:

`M95_GATE=BLOCKED`

The remaining accepted-scope findings were:

- F05 HIGH - public raw registered fresh-execution persistence phases could
  bind and execute an ExperimentSpec without proving frozen StudyRevision
  compatibility;
- F04 MEDIUM - canonical validation still admitted negative transaction cost,
  drawdown below `-1` with nonnegative equity and partial execution
  event/price/quantity tuples;
- F06 MEDIUM - restart recovery could persist a job/Trial/event terminal time
  earlier than the linked RunAttempt creation time;
- F03 LOW - current-state documentation still lagged the published/audited
  state.

M9.4l is the bounded follow-up correction. It makes raw registered
fresh-execution persistence phases internal behind the claimed-job authority
that already validates frozen registered execution inputs; adds only the
remaining direct canonical invariants; and uses one coherent restart-recovery
timestamp floored by linked RunAttempt creation for attempt, ResearchJob,
Trial and disposition-event chronology.

## 12. M9.4l publication, independent audit and M9.4m

M9.4l was published/post-push verified at `d26d3d62b6e7cced738bdbf260269497e0e70d5d`. Its local validation included 176 focused tests, 207 research-only M9.4 tests across 13 modules and 1383 complete Python tests. The independent reviewer subsequently discovered 273 repository-wide M9.4 tests across 21 modules and independently ran all 1383 Python tests. The audit returned `M95_GATE=BLOCKED` with A01, A02, A03 and F03. Publication and passing tests did not establish independent acceptance.

At the 2026-10-11 pre-publication validation checkpoint, M9.4m was a local, unstaged and unpublished corrective candidate. This is a historical checkpoint statement, not an assertion about its eventual publication state. A01 adds direct canonical financial consistency checks for net/gross/cost and single-symbol close-marked equity. A02 includes durable cancellation-request time in the shared restart-recovery terminal timestamp. A03 separates public standalone prepared execution from internal supplied-RunAttempt execution and rejects stale attempts before computation; a concurrent claimed-job test verifies one physical execution through that supported entry path. Existing M4 Backtest economics, M5 WFA, M6/M7 Paper causality, M8 application authority, M9.3 data truth and the no-live-order boundary are retained.

Local M9.4m validation passed 1394 complete Python tests and 280 repository-wide M9.4 tests across 21 modules; `git diff --check` passed. At the 2026-10-11 pre-publication checkpoint, `M95_GATE=BLOCKED`. The required release sequence is final review, separately approved stage, commit and push, verification of the exact published HEAD, and a fresh independent post-publication M9.4 audit. Only an explicit `M95_GATE=PASS` for the audited published HEAD authorizes fresh M9.5 design; it does not authorize M9.5 implementation.
