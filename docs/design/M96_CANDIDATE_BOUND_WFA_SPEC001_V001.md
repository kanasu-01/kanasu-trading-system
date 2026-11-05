# M9.6 — Historically Eligible Strategies to Walk-Forward Analysis

**Proposed specification:** `KTS-M009-S006-SPEC001-V001`

**Status:** PROPOSED for human review. This wording does not authorize implementation until it completes the required controlled review and approval process.

**Purpose:** Take strategies that have passed Historical Backtest validation, evaluate each exact strategy independently through the existing validated Walk-Forward Analysis system, preserve the resulting evidence, and identify which strategies are eligible to proceed to the later qualified Paper Trading stage.

## Terms used in this specification

### Historically Eligible Strategy

A **Historically Eligible Strategy** is one exact strategy setup that has passed Historical Backtest validation.

The exact setup includes the registered strategy procedure and the exact configuration that was historically validated. Passing Historical Backtest validation does not mean that the strategy has passed WFA or is ready for qualified Paper Trading.

Internally, the existing fixed candidate identity continues to preserve the exact technical identity and lineage. This specification does not require renaming that existing internal model.

### WFA Eligible Strategy

A **WFA Eligible Strategy** is a Historically Eligible Strategy whose valid completed Walk-Forward Analysis returns the existing WFA `PASS` verdict.

A WFA Eligible Strategy may be considered by the later qualified Paper Trading stage. WFA eligibility does not itself start Paper Trading.

## What happens

```text
Registered Historical Backtests
             ↓
Historical Backtest Validator
             ↓
Historically Eligible Strategies
             ↓
        WFA stage starts
             ↓
Load the Historically Eligible Strategies
for the selected registered research scope
             ↓
Evaluate each exact strategy independently
using the existing validated WFA engine
             ↓
Existing WFA internally creates its
rolling train/test windows
             ↓
Persist each strategy's WFA evidence
and result
             ↓
        WFA PASS / FAIL
          ↙         ↘
WFA Eligible      Not WFA Eligible
   Strategy
      ↓
Later qualified Paper Trading stage
```

## Behaviour — step by step

### 1. Load the strategies that passed Historical Backtest validation

When the WFA stage starts for a selected registered research study version, Kanasu loads the strategies in that scope that are currently Historically Eligible.

A strategy that is historically rejected, insufficient, invalid, missing a current eligible decision, or otherwise not currently Historically Eligible must not enter WFA.

Current historical eligibility must still be true when a WFA decision is durably written. The active qualification activation must still resolve to an actual valid immutable QualificationPolicy record whose canonical identity, version and threshold agree with the current eligible Historical Backtest decision. A missing, malformed or contradictory active policy record, a policy activation change, or a newer Historical Backtest qualification decision that makes the strategy non-current must prevent a new WFA decision from being persisted against stale or unverifiable eligibility. Equivalent Decimal text that represents the same canonical threshold value does not by itself create a different policy.

The WFA stage may therefore receive one strategy, many strategies, or no strategies. The design is not limited to a single strategy.

### 2. Keep every eligible strategy exactly as it was validated

Each Historically Eligible Strategy must enter WFA with the same exact registered strategy setup that passed Historical Backtest validation.

Kanasu must preserve the strategy procedure, exact strategy parameters, instrument, timeframe, initial capital, applicable risk/economic configuration and applicable data-treatment settings that belong to that validated strategy.

The historical result-bearing Trial must still resolve to the same current causing ResearchJob, RunAttempt or exact-reuse source, accepted ResearchEvidence, Backtest result and registered manifest/configuration that supported the Historical Backtest qualification decision. An identical result hash from a different current attempt/evidence lineage is not sufficient.

For example, if an SMA strategy passed Historical Backtest validation with `fast_period = 10` and `slow_period = 30`, WFA must evaluate that same `10/30` strategy. It must not silently replace it with `20/50` or another configuration.

### 3. Use the strategy's registered historical dataset

WFA uses the registered historical data belonging to the Historically Eligible Strategy.

The WFA input must remain attributable to the same authoritative historical research data identity and assumptions that belong to that strategy. When a Historical Backtest qualification decision is written and its accepted evidence contains exactly one canonical DatasetReference, Kanasu freezes that exact DatasetReference artifact ID in a durable qualification-admission binding. M9.6 requires that frozen admission, the original physical bytes and canonical dataset-ID binding to remain verifiable. Editing the later ResearchEvidence reference list or supplying a different artifact with equivalent candles or dataset identity cannot replace the exact DatasetReference that was admitted with the historical qualification. Older/unbound qualification decisions are not repaired by guesswork; they cannot establish M9.6 dataset admission authority until a later supported historical qualification produces a durable binding.

Historical Backtest validation may already have examined performance over this historical research dataset. Therefore Kanasu must not describe the entire WFA dataset as a completely untouched final holdout merely because WFA later divides it into train/test windows.

### 4. Let the existing WFA system perform the data splitting

Kanasu does not manually create new WFA periods after seeing performance.

The existing WFA engine receives the applicable historical candle sequence and deterministically divides it into its existing rolling in-sample and out-of-sample windows.

The currently validated WFA configuration remains the existing rolling configuration:

- 300 in-sample bars;
- 150 out-of-sample bars;
- 150-bar step.

A separately approved future change may change the WFA configuration. This specification does not change it. The durable WFA writer must derive these approved settings from the existing `WALK_FORWARD_CONFIG`; agreement between caller-supplied configuration values and a caller-supplied fingerprint is not authority.

Within WFA, “out-of-sample” means that the test bars of a WFA window are not used by that window's in-sample selection process. It does not mean that the whole historical dataset was necessarily unseen during all earlier research activity.

### 5. Reuse the existing validated WFA engine

M9.6 does not build another Walk-Forward Analysis engine.

Kanasu reuses the existing validated WFA window generation, Backtest execution, metrics, stitched equity calculation and existing final WFA `PASS` / `FAIL` verdict.

Accepted Backtest and WFA financial mathematics remain unchanged.

Saved WFA evidence must remain consistent with those existing calculations. Per-window account P&L, account return and drawdown must agree with the persisted OOS equity curve without a tolerance that can cross an existing M5 categorical boundary such as exactly zero versus positive return; the window's opening equity must preserve the registered initial-capital semantics. Stored trade-summary identities that are directly derivable from the stored summary fields must not contradict themselves. Existing M4 definitions remain authoritative: positive/negative instrument-return summaries are not interchangeable with net profitable/losing trade counts because transaction costs can change net profitability without changing the instrument-return sign. The overall mean instrument return must lie between the stored mean negative and mean positive instrument returns; this is a direct arithmetic bound from the same M4 summary fields, not a new economic gate. Existing M4 accounting also requires non-negative transaction costs not to make net realized P&L exceed gross realized P&L; zero transaction cost preserves exact gross/net equality. Only mathematically implied net-total sign constraints may be enforced when all completed trades are winners, all are losers, or all are breakeven; mixed winners and losers may legitimately produce a positive, zero or negative total. These are evidence-integrity checks, not new economic qualification rules.

### 6. WFA must test the exact Historically Eligible Strategy

For each Historically Eligible Strategy, the WFA parameter input contains only that strategy's exact registered parameter configuration.

The existing WFA execution path may still use its normal optimizer machinery internally, but it must have no alternative parameter configuration from which to select.

Therefore the strategy evaluated in every WFA test window remains the same exact strategy configuration that passed Historical Backtest validation.

The existing general multi-parameter WFA search space must not silently replace or modify the Historically Eligible Strategy.

### 7. Evaluate multiple strategies independently

Each Historically Eligible Strategy is evaluated independently.

A PASS, FAIL, insufficient result, invalid result or ordinary strategy-specific failure for one strategy must not determine the result of another strategy.

The initial MVP implementation may evaluate the strategies sequentially. Parallel or distributed WFA execution is not required.

### 8. Keep the existing WFA PASS / FAIL rules

M9.6 adds no new economic qualification criteria.

It does not add Sharpe ratio, Sortino ratio, profit factor, minimum trade count, benchmark performance, parameter-sensitivity thresholds, additional cost-stress thresholds, regime thresholds or other new qualification rules.

For valid and sufficient WFA evidence:

- existing WFA `PASS` means the strategy becomes WFA Eligible;
- existing WFA `FAIL` means the strategy is not WFA Eligible.

The existing WFA verdict remains authoritative for this MVP stage.

### 9. Do not misrepresent the singleton optimizer stability value

When WFA receives only one exact parameter configuration, the existing optimizer may naturally report a perfect optimization-stability value because there were no competing parameter configurations.

That value must not be presented as proof that the strategy has demonstrated parameter robustness or sensitivity stability.

M9.6 does not add a separate parameter-stability qualification test.

### 10. Keep poor performance, insufficient evidence, invalid evidence and operational failure separate

A genuine completed WFA `FAIL` is a strategy result.

Not enough historical bars to produce the required WFA windows is `INSUFFICIENT`, not a strategy rejection. Before either an incomplete-retrieval or too-few-bars `INSUFFICIENT` decision is recorded, the exact DatasetReference frozen with the historical qualification must still be the admitted reference, retain its durable dataset-ID binding, remain physically verifiable, and its decoded candle sequence must reproduce the historical ExperimentSpec dataset fingerprint using the existing canonical dataset-fingerprint function. The historical result-bearing Trial must also still resolve to the same current successful causing Job/RunAttempt or exact-reuse lineage and ACCEPTED ResearchEvidence that supported qualification. Missing, contradictory, replaced, corrupt, rejected or stale authority is not classified as insufficient history.

Contradictory or unverifiable strategy, data, configuration or evidence identity is `INVALID`, not a poor-performance result.

A database, filesystem, provider, service or similar operational failure that prevents reliable evaluation is an operational failure. Git/executable-compatibility infrastructure failures such as permission failure, timeout, unavailable Git, an unavailable repository revision, or unknown worktree-cleanliness status are also operational failures. They must not be converted into fabricated WFA `FAIL` or `INVALID` strategy outcomes. A positively observed dirty worktree or a proven incompatible executable state remains deterministic invalidity rather than an operational failure.

### 11. Save the WFA evidence for every evaluated strategy

Kanasu must durably record enough information to establish what was actually evaluated and what WFA concluded.

For each strategy, the saved WFA evidence must be attributable to:

- the exact Historically Eligible Strategy;
- the Historical Backtest validation decision that allowed it to enter WFA;
- its registered historical data identity and range;
- the strategy's exact registered configuration;
- the WFA configuration actually used;
- the WFA window boundaries;
- the WFA results and metrics required to support the existing verdict;
- the final WFA verdict;
- the software/evaluator identity needed by the accepted research-evidence contract.

CandidateWfaService is the supported M9.6 classification authority. The SQLite WFA writer is an internal persistence primitive, not a second public evaluator that may accept caller-authored INVALID or INSUFFICIENT outcomes. Before a durable WFA decision is appended, the service establishes the classification and the internal writer independently rechecks the transactional authorities that can race or be corrupted at persistence. For `INSUFFICIENT`, that recheck includes canonical current M9.5 decision/policy identity, exact Candidate/Trial/current Job/RunAttempt-or-reuse/ACCEPTED-evidence/result lineage, the exact frozen historical DatasetReference admission, its physical canonical bytes, dataset-ID binding and historical dataset fingerprint. Economic decisions continue through the stronger result-artifact and current evaluator/executable checks. This revalidation does not rerun historical economics or add a new qualification gate.

Previous historical research evidence must not be rewritten merely because WFA was later performed.

### 12. Preserve each WFA result rather than rewriting history

A completed WFA evaluation is historical research evidence.

A later WFA evaluation, if separately permitted in the future, must not silently overwrite or rewrite an earlier completed WFA result.

The MVP implementation needs only the minimum durable candidate-bound WFA result and decision required for truthful progression. It does not require a general-purpose WFA workflow-management framework.

### 13. Passing WFA permits later Paper consideration only

A WFA `PASS` makes that exact Historically Eligible Strategy a WFA Eligible Strategy.

This means only that the exact same strategy may be considered by the later qualified Paper Trading stage.

The WFA stage does not automatically:

- create a Paper campaign;
- start a Paper session;
- place a simulated Paper trade;
- place a real-money order.

Qualified Paper Trading remains a separate later stage.

### 14. Keep the MVP implementation small

The first implementation supports the research progression that is currently required:

```text
Historically Eligible Strategies
        ↓
existing WFA
        ↓
durable strategy-bound WFA evidence
        ↓
WFA eligibility
```

The initial implementation does not require:

- a distributed WFA scheduler;
- parallel worker infrastructure;
- candidate leaderboards;
- automatic strategy ranking;
- adaptive-candidate support;
- parameter-search redesign;
- configurable WFA rule builders;
- automatic Paper start;
- frontend integration;
- public HTTP WFA control endpoints;
- live-money trading.

Those capabilities require separate future scope if they become necessary.

## Existing behaviour that must remain unchanged

This specification does not reopen or redefine:

- accepted Backtest execution, timing, fills, costs, accounting or risk behaviour;
- existing WFA window mathematics, metrics, stitched-equity calculations or PASS/FAIL rules;
- existing historical-data truthfulness and canonical instrument/provider boundaries;
- Historical Backtest validation criteria;
- existing Paper Trading causality or runtime behaviour;
- the prohibition on real-money trading in MVP V1.

## Minimum acceptance checks

The implementation must demonstrate at least the following behaviour:

1. Starting WFA for a selected registered research scope loads all currently Historically Eligible Strategies in that scope rather than being permanently limited to one strategy.
2. A strategy that has not passed current Historical Backtest validation cannot enter WFA.
3. Historical eligibility is rechecked at durable WFA persistence so the active policy activation must still resolve to a valid canonical QualificationPolicy row and the latest matching Historical Backtest decision; missing, contradictory or stale policy/decision authority cannot create a WFA decision.
4. Each loaded strategy is evaluated independently.
5. The exact registered strategy configuration that passed Historical Backtest validation is preserved.
6. Current historical causing-job, RunAttempt/reuse, evidence and result lineage still match the exact Historical Backtest qualification decision.
7. The historical manifest/configuration still matches the registered strategy parameters, capital, risk/economic settings and repository revision.
8. The normal general WFA parameter search cannot silently replace the fixed strategy with another configuration.
9. WFA uses the exactly-one historically admitted DatasetReference; missing original bytes/reference/binding cannot be repaired by a substitute artifact.
10. The existing WFA engine performs its existing deterministic rolling 300/150/150 window splitting, and the public writer independently requires that approved configuration.
11. Warm-up, window boundaries, scored timestamps and singleton parameter evidence match existing M5 generation from the admitted candles.
12. Each window preserves the registered initial-capital semantics.
13. Persisted account P&L, return and drawdown agree exactly with the persisted OOS equity-derived M4 values at categorical boundaries such as zero versus positive return; a tolerance must not fabricate profitability.
14. Directly derivable completed-trade summary identities are internally consistent while preserving M4 distinctions between instrument-return sign and net profitability; impossible all-winner/all-loser/all-breakeven net-total signs are invalid, while mixed winners and losers may have any total sign.
15. Existing WFA aggregate, exact stitched-equity and PASS/FAIL mathematics remain unchanged.
16. Existing WFA `PASS` produces WFA eligibility for that exact strategy.
17. Existing WFA `FAIL` does not produce WFA eligibility.
18. Insufficient bars produce `INSUFFICIENT`, not `FAIL`.
19. Invalid or contradictory identity/evidence produces `INVALID`, not `FAIL`.
20. Database/filesystem/provider failures, unavailable Git/repository identity, unknown worktree cleanliness and Git compatibility infrastructure failures remain operational and do not fabricate strategy outcomes; an observed dirty worktree or proven incompatibility remains deterministic invalidity.
21. Candidate-bound WFA evidence and the final result survive persistence/reload according to the accepted research persistence contract.
22. The saved result identifies the exact strategy, historical validation lineage, original admitted data, approved WFA configuration, trusted evaluator revision and WFA result used.
23. Caller-supplied evaluator revision text cannot establish its own authority.
24. A singleton optimizer-stability value is not represented as independent parameter-robustness evidence.
25. One strategy's result does not determine another eligible strategy's result.
26. WFA eligibility does not automatically start Paper Trading.
27. No real-money execution path is created.
28. Existing M9.5, schema/queue and complete WFA regression behaviour remains green, and substitution tests accept the earliest authoritative rejection rather than depending on a later internal failure message.

## Technical mapping note

The human-language term **Historically Eligible Strategy** does not replace the existing internal fixed candidate model.

At implementation level, it corresponds to the existing exact fixed candidate identity together with its current eligible Historical Backtest qualification state.

The human-language term **WFA Eligible Strategy** describes the progression status of that same exact strategy after a valid completed WFA `PASS`. It does not imply that a second strategy object or renamed strategy class must be introduced.
