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

The M9.4j corrective working tree is not yet staged, committed or pushed.

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

The integrated unpublished M9.4j corrective working tree was validated as one
package after R01-R06 were present together.

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

These validation results establish a local corrective candidate only. They do
not constitute publication, independent acceptance or M9.5 authorization.

## 10. Remaining publication and independent-audit requirements

Before M9.4j can be accepted as the new M9.4 closure state:

1. review the exact changed-file manifest and final diff hygiene;
2. obtain separate explicit human approval for staging;
3. validate the exact staged manifest;
4. obtain separate explicit human approval for commit;
5. verify the resulting local corrective commit;
6. obtain separate explicit human approval for push;
7. verify the exact local and remote corrective HEAD after push;
8. perform a fresh independent M9.4 audit against that exact published HEAD.

Only:

`M95_GATE=PASS`

authorizes fresh M9.5 design.

A PASS authorizes M9.5 design only; M9.5 implementation remains separately
approved work.
