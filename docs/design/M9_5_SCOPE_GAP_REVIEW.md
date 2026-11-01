# KANASU — M9.5 MVP V1 Scope Discovery and Proposed Minimal Gate

**Document status:** PROPOSED DISCOVERY RECORD — NOT AUTHORITATIVE; NOT ADMITTED
**Project:** Kanasu Trading System
**Version / Phase / Milestone:** V1 / P5 / M9.5
**Document purpose:** Identify genuine M9.5 implementation gaps before controlling a separate admission/design amendment.
**Reviewed project branch:** `m9-v1-research-platform`
**Source commit:** `b59c3377d2c99961b9f2d082dbf4e6831ab90384`
**Global SOP registry branch:** `kanasu-01/kanasu-sops` / `main`
**SOP registry commit:** `64d5e86e9c2895db4ffd9caf39bc998d84fbc721`

## 1. Authority and limitations

M9.4q has received the project owner's final Human Approval 3 at the source commit above, on Governance §7.1's bounded prospective basis. Historical `NOT_VERIFIED` findings remain unresolved historical gaps and are not reclassified.

The current M9.5 roadmap remains `PLANNED; FORMAL ADMISSION REQUIRED; IMPLEMENTATION NOT AUTHORIZED`. The owner has expressed a design direction, not authorized implementation or changed the existing accepted architecture.

Previous M9.5 Draft v0.3, Gate-A and Draft 004 material is proposal/review history; its mere existence or reported review does not confer publication or implementation authority. An earlier proposed `SPEC001` concerning registered StudyRevision modification protection was withdrawn as already implemented. Do not revive or reserve its identifier through this record.

This document is a *read-only gap-analysis and proposed minimal-scope record*. Publication of this record alone would not admit M9.5, supersede accepted AD-021, amend V1 release gates, establish an ACTIVE behavioral specification, or authorize code, schema, API, WFA, Paper, or other implementation changes.

## 2. Verified existing implementation: do not rebuild

1. `core/backtest/performance_metrics.py`: `PerformanceMetrics.summarize_backtest()` already calculates `completed_trade_count`, `net_profitable_trade_count` and `net_profitable_trade_rate_pct`.
2. The existing metric treats a completed trade as profitable only if its **net monetary trade P&L is strictly positive**, after the applicable transaction-cost accounting. Completed losing and breakeven trades remain in the denominator. It returns 0 for zero completed trades.
3. `tests/backtest/test_performance_metrics.py` tests the metric and trade classifications, including breakeven behavior.
4. `core/research/registered_study_registration.py`, `core/research/models/registered_study.py` and `core/research/sqlite_research_catalog_store.py` already provide registered, immutable StudyRevision and Trial lineage. Existing tests verify idempotent repeated registration and successor revision identity for material changes.
5. `core/research/research_artifact_store.py` persists canonical Backtest-result artifacts; `core/research/reproducibility.py` validates their canonical bytes; `core/research/study_aggregation.py` resolves registered result artifacts and validates evidence, but provides descriptive aggregation, not strategy qualification.
6. `api/backtest_application.py` already exposes the authoritative Backtest summary. Do not add a competing profitability calculator or redefine existing Backtest financial results.

## 3. Genuine missing M9.5 behavior

| Candidate capability | Observed current state | M9.5 implication |
|---|---|---|
| Net-profitable trade-rate metric | IMPLEMENTED in M4 | REUSE; not new M9.5 work |
| Immutable registered StudyRevision | IMPLEMENTED in M9.2/M9.4 | REUSE; withdrawn old SPEC001 stays withdrawn |
| Canonical result and evidence persistence | IMPLEMENTED in M9.2/M9.4 | REUSE authoritative result and evidence lineage |
| Evaluate a versioned 50% gate | NOT IDENTIFIED in current milestone-branch implementation | GENUINE NEW BEHAVIOR |
| Durable, attributable qualification decision | NOT IDENTIFIED in current milestone-branch implementation | GENUINE NEW BEHAVIOR |
| Minimum fixed CandidateRevision bound to exact evidence | Not identified as implemented | GENUINE NEW M9.5/M9.6 INTERFACE |
| Actually launch WFA or Paper | Existing WFA/Paper computation cores; research progression not implemented | M9.6/M9.7; NOT M9.5 |

The gap findings are based on targeted inspection of the exact committed repository tree, relevant code, tests and accepted documentation. They do not claim that every possible runtime path was dynamically exercised. No tests were executed in this read-only review.

## 4. Owner-selected proposed MVP V1 gate

**Exactly one proposed strategy-qualification criterion:**
`net_profitable_trade_rate_pct >= 50.0`

Source is the existing authoritative Backtest metric for the exact selected and verified registered historical Backtest/Trial evidence. The numerator counts completed trades with net `trade.pnl > 0`; the denominator counts **all completed trades**, including losing and breakeven trades. No rounded display value is used for comparison.

Proposed outcomes:
- `ELIGIBLE`: valid selected evidence, one or more completed trades, and rate **at least** 50%.
- `REJECTED`: valid selected evidence, one or more completed trades, and rate **below** 50%.
- `INSUFFICIENT`: no completed trades or required evidence is unavailable; not eligible.
- `INVALID`: evidence is present but fails mandatory integrity or identity checks; not eligible.
- An operational evaluation error is not silently converted to a successful eligibility decision.

An ELIGIBLE decision means permission to *consider the exact unchanged CandidateRevision for M9.6 WFA*. It is not a profitability assurance, WFA success, Paper authorization, or permission to place real-money orders.

The criterion is deliberately a **winning-trade percentage**, not net account return, total net monetary profit, profit factor or professional robustness validation. A strategy may satisfy the 50% winning-trade criterion yet have negative overall net P&L. This is an explicitly accepted limitation of the proposed educational/workflow MVP gate.

A valid historical Backtest with only one completed winning trade would pass this one criterion. A minimum sample-size threshold would be an additional criterion and is not introduced here.

## 5. Minimal implementation direction — not yet authorized

Later approved implementation can reuse existing research artifacts, authoritative result validation, registration and storage, rather than building another research engine.

Only the following necessary new responsibilities are presently contemplated:
1. An immutable versioned policy identifying the single fixed criterion and its threshold.
2. A deterministic evaluator resolving exact eligible evidence and applying that criterion.
3. An append-only attributable decision with observed counts/rate, policy identity, evidence identity and outcome.
4. A minimum fixed CandidateRevision link sufficient for M9.6 to consume the same exact strategy/configuration and evidence.

This is not a full specification of their schemas, concurrency contracts, endpoint shapes or persistence operations. Those changes require later exact-file inspection, a separate precise natural-language specification, the canonical candidate, human inspection, independent Review 1, approved guarded implementation, actual-state Review 2 and final human acceptance.

Do not assume that aggregate percentages over independently simulated Trial accounts are one strategy's trade rate. In the first minimal slice, a **specifically identified single valid Trial/Backtest result** is the proposed evaluation target. Selection among multiple Trials must be explicit and attributable; no hidden best-run search or post-hoc aggregation is authorized.

## 6. Mandatory truth and accepted architectural boundaries

Existing Backtest economic correctness, immutable evidence, registered research lineage, WFA mathematics, Paper simulated-execution causality, supported timeframes and the no-real-money boundary remain unaffected. `ResearchEvidenceStatus.ACCEPTED` is not research qualification.

Accepted AD-021 and the current V1 release-validation plan presently describe broader robustness, parameter sensitivity, cost stress, temporal/market evidence and related qualification controls. The owner's desired minimal gate is a **proposal to narrow V1 qualification scope**, not a silent repeal of those accepted obligations.

A subsequent *separately controlled* design/admission candidate must identify the exact conflicting original paragraphs, show exact old/new comparisons, preserve earlier approved history, establish which requirements remain mandatory for integrity, and explicitly defer or retain the remaining robust-evaluation requirements with human approval.

The proposed future placement of broader criteria is later MVP version work, not an automatic claim that an existing accepted V1 release gate has already been changed.

M9.6 owns Candidate-bound WFA/OOS confirmation and M9.7 owns qualified Paper campaigns under the currently accepted roadmap. Any decision to combine or resequence them requires its own approval.

## 7. Proposed incremental order

1. **M9.5 admission/design reconciliation** — exact revisions to owning roadmap, AD-021, release validation and deferred-work documents; documentation-only.
2. **One-metric evaluation specification** — exact selected-result identity, strict 50% comparison and missing/invalid evidence behavior.
3. **Minimal durable policy and decision specification** — no configurable multi-criterion framework.
4. **Minimal fixed Candidate handoff specification** — no automatic WFA or Paper launch.
5. **Bounded validation and closure** — focused evidence and preserved existing regressions.

Existing permanent identifiers and the SOP-G-003 hierarchy must be respected. This discovery document does not reserve a new permanent Step/Specification number.

## 8. Explicit non-goals

No additional threshold for minimum trades, aggregate net return, profit factor, Sharpe, Sortino, drawdown, loss ratios, sample sufficiency, parameter stability, cost/slippage stress, cross-market robustness, statistical confidence or AI evaluation.

No general rule builder, advanced scoring dashboard, historical Backtest refactor, WFA computation change, real-money broker order, automatic Paper progression or hidden change of established accepted architecture.

## 9. Verification and future change controls

Before any later Git publication:
- Reverify the correct milestone branch and expected parent HEAD.
- Retrieve exact current versions of every document proposed for modification.
- Compare every changed original block and every complete proposed successor in the required HTML CCRF.
- Include exact file operations, content hashes, tests/verification, protected Git operation order and fail-closed stop conditions.
- Obtain the applicable human inspection, independent reviews and final acceptance.

**Current result:** READ-ONLY GAP ANALYSIS PREPARED. M9.5 remains NOT_ADMITTED. NO IMPLEMENTATION IS AUTHORIZED.
