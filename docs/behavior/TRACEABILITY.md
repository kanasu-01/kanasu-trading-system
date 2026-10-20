# Kanasu Behavioral Traceability

## Purpose

Behavioral traceability lets the product owner review meaningful system behavior in natural language while technical review verifies that implementation and tests actually match that behavior.

It does not replace source-code review, automated tests or specialist inspection for numerical, concurrency, security or resource-management defects.

## Stable identifiers

Use durable identifiers by area:

- `DATA-FLOW-*`, `DATA-RULE-*`
- `BT-FLOW-*`, `BT-RULE-*`
- `WFA-FLOW-*`, `WFA-RULE-*`
- `PAPER-FLOW-*`, `PAPER-RULE-*`
- `RESEARCH-FLOW-*`, `RESEARCH-RULE-*`
- `SAFETY-RULE-*`

Do not silently renumber accepted identifiers. A superseded item keeps its ID and points to the replacement.

## Verification states

A behavior is:

- `DESIGNED` when its intended contract is accepted;
- `IMPLEMENTED` when implementation exists but trace verification is incomplete;
- `VERIFIED` only after implementation and appropriate test/evidence traces are checked;
- `DEFERRED` when deliberately outside current scope;
- `SUPERSEDED` when replaced while preserving history.

Documentation text alone cannot establish `VERIFIED`.

## Required change declaration

Every implementation slice from M9.2 onward declares exactly one primary impact:

~~~text
BEHAVIOR IMPACT: NONE
BEHAVIOR IMPACT: ADDED
BEHAVIOR IMPACT: CHANGED
BEHAVIOR IMPACT: REMOVED
~~~

For non-`NONE` impact, record:

- affected behavior IDs;
- behavior before;
- behavior after;
- rationale;
- user/research impact;
- implementation paths/symbols;
- tests/evidence proving the behavior;
- adjacent invariants that must remain unchanged.

`BEHAVIOR IMPACT: NONE` is also reviewable. If code changes meaningful behavior, the declaration must be corrected before acceptance.

## Review gate

~~~text
accepted behavior before
        |
        v
authorized implementation
        |
        v
behavior after
        |
        v
natural-language behavior delta
        |
        v
implementation trace
        |
        v
test/evidence trace
        |
        v
independent deviation review
        |
        v
product-owner behavioral review
~~~

## Initial traceability map

| Behavior ID | Natural-language behavior | Primary implementation evidence | Verification evidence | Status |
|---|---|---|---|---|
| DATA-RULE-001 | Missing history is not silently invented | `core/market_data/historical_source.py`, historical retrieval/coverage boundaries | `test_local_only_reports_exact_missing_ranges_without_factory`; `test_old_local_coverage_cannot_mask_partial_provider_evidence` | VERIFIED |
| DATA-RULE-002 | Fully covered LOCAL_FIRST avoids provider creation | `HistoricalSource._retrieve_local_first()` | `test_local_first_returns_warm_cache_without_factory` | VERIFIED |
| DATA-RULE-003 | Historical provider bindings are explicit, effective-dated and unambiguous | `core/market_data/provider_instrument_binding.py`; `core/market_data/instrument_registry.py` | `test_transition_splits_request_into_exact_subranges`; `test_gap_fails_clearly`; `test_overlap_fails_clearly`; `test_registry_preserves_binding_transition_subranges` | VERIFIED |
| DATA-RULE-004 | Provider wall-time formatting preserves canonical request/timestamp identity | `core/broker/angelone.py`; `core/market_data/binding_aware_historical_feed_provider.py` | `test_aware_non_ist_bounds_are_converted_to_india_wall_time`; `test_explicit_provider_binding_drives_token_and_exchange` | VERIFIED |
| DATA-RULE-005 | Dataset identity/provenance evolution is versioned and incompatible acquisition streams are not silently mixed | `core/research/models/dataset.py`; `core/market_data/sqlite_candle_store.py`; `core/research/successor_historical_retrieval.py` | `test_successor_schema_does_not_redefine_dataset_v1`; `test_incompatible_acquisition_streams_have_distinct_identity`; `test_multi_binding_request_uses_separate_streams`; `test_successor_retrieval_ignores_legacy_v1_cache` | VERIFIED |
| BT-RULE-001 | Completed-bar decisions follow accepted next-interval execution | Backtest execution/engine boundaries | `test_backtest_queues_completed_bar_signals_for_following_open` | VERIFIED |
| BT-RULE-002 | Backend execution/portfolio state owns financial truth | execution/portfolio/Backtest result boundaries | `test_backtest_reports_authoritative_execution_portfolio_state`; frontend `BacktestPage.test.tsx` ? `submits the authoritative request and renders the response` | VERIFIED |
| WFA-RULE-001 | OOS does not select preceding parameters | `core/walk_forward/runner.py`, window/optimizer boundaries | `test_m5_5_end_to_end_wfa_validity_chain`; accepted M5 window/runner regression | VERIFIED |
| PAPER-RULE-001 | Clock alone cannot create a Paper fill | Paper processor/live runtime | `test_wall_clock_does_not_advance_source_event_watermark`; `test_clock_advance_alone_cannot_execute_pending_live_intent` | VERIFIED |
| PAPER-RULE-002 | Historical reconciliation cannot create retrospective Paper trades | live Paper reconciliation path | `test_live_reconciliation_replays_history_without_creating_trade_intent`; `test_live_reconciliation_with_open_position_uses_history_for_state_only` | VERIFIED |
| SAFETY-RULE-001 | Supported V1 application has no real-money order path | M8 application composition and dormant/unimplemented live path | M8 validation evidence | VERIFIED |
| RESEARCH-RULE-001 | Tested research lineage is retained | `core/research/sqlite_research_catalog_store.py`; `api/research_application.py` | `test_explicit_retry_preserves_trial_spec_and_prior_failure_history`; `test_trial_detail_exposes_durable_disposition_job_and_result_lineage`; `test_list_trials_exposes_current_dispositions_without_filtering` | VERIFIED |
| RESEARCH-RULE-002 | Policy changes do not rewrite evidence | future qualification service | future M9 tests | DESIGNED |
| RESEARCH-RULE-003 | Execution success and research qualification are distinct | future M9 state model | future M9 tests | DESIGNED |
| RESEARCH-RULE-004 | Independent universe accounts are not presented as a portfolio | `core/research/study_aggregation.py`; `api/research_application.py` | `test_aggregation_reports_explicit_denominators_and_partial_failures`; `test_aggregation_resolves_executed_and_reused_result_lineage`; `test_aggregation_delegates_independent_account_service` | VERIFIED |
| RESEARCH-RULE-005 | Candidate progression preserves exact lineage and WFA-before-Paper stage order | future Candidate/WFA/Paper application services | future M9 tests | DESIGNED |
| RESEARCH-RULE-006 | Universe quality, provenance and effective membership constrain historical claims | `core/research/models/universe.py` | `test_mixed_historical_quality_remains_visible`; `test_current_snapshot_can_be_used_with_non_pit_semantics`; `test_point_in_time_mode_rejects_current_snapshot` | VERIFIED |
| RESEARCH-FLOW-001 | Application Backtests create durable execution/evidence lineage without changing financial authority | `api/backtest_application.py`; `core/research/backtest_research_orchestrator.py` | `test_application_runs_real_backtest_from_local_history`; `test_application_exposes_incomplete_identity_without_attempt` | VERIFIED |
| RESEARCH-FLOW-002 | Explicit successor Backtest application context attaches canonical DatasetReference truth while the default Backtest path remains legacy | `api/backtest_application.py`; `core/research/successor_backtest_research_coordinator.py`; `core/research/successor_historical_retrieval.py` | `test_opt_in_successor_path_attaches_dataset_reference_without_legacy_source`; `test_default_application_path_remains_legacy_when_successor_context_absent`; `test_successor_execution_attaches_dataset_reference_and_uses_exact_candles` | VERIFIED |
| RESEARCH-RULE-007 | Fingerprinted Backtest candles are the exact candles executed | `core/research/backtest_research_orchestrator.py`; `core/research/claimed_research_job_executor.py`; `core/research/claimed_trial_execution_inputs.py` | `test_clean_execution_uses_one_exact_candle_sequence_and_accepts_evidence`; `test_m94h1_manifest_io_race_executes_verified_private_snapshot`; `test_m94h1_retrieval_mutation_cannot_change_registered_capital`; `test_m94h1_rejects_unrelated_strategy_using_same_procedure_label` | VERIFIED |
| RESEARCH-RULE-008 | Retries preserve ExperimentSpec identity while receiving distinct RunAttempt identity | `core/research/sqlite_research_catalog_store.py`; `core/research/reproducibility.py` | `test_equivalent_spec_reuses_identity_and_first_creation_time`; `test_retries_use_distinct_attempt_ids_for_same_spec` | VERIFIED |
| RESEARCH-RULE-009 | Failed/incomplete evidence cannot become accepted reproducibility evidence | `core/research/models/research_evidence.py`; `core/research/backtest_research_orchestrator.py`; `core/research/sqlite_research_catalog_store.py` | `test_accepted_evidence_requires_all_three_fingerprints`; `test_execution_failure_creates_failed_evidence_and_failed_attempt`; `test_terminal_persistence_failure_does_not_claim_durable_success`; `test_m94l_exact_reuse_rejects_additional_canonical_counterexamples`; `test_m94m_hash_valid_financial_contradictions_block_aggregation` | VERIFIED |
| RESEARCH-RULE-010 | Exact executable software identity gates ExperimentSpec/RunAttempt creation and accepted automatic evidence | `core/research/software_identity.py`; `core/research/backtest_research_orchestrator.py` | `test_clean_repository_identity_is_exact`; `test_dirty_repository_identity_is_not_exact`; `test_unknown_revision_does_not_query_worktree_status`; `test_nonexact_software_identity_never_fabricates_spec_or_attempt` | VERIFIED |
| RESEARCH-RULE-011 | Canonical instrument lineage is independent of ticker/provider identity | `core/entities/instrument.py`; `core/market_data/provider_instrument_binding.py`; `core/market_data/instrument_registry.py` | `test_binding_keeps_provider_identity_separate_from_instrument_identity`; `test_registry_preserves_effective_dated_symbol_change` | VERIFIED |
| RESEARCH-RULE-012 | Point-in-time universe evidence cannot apply a future membership state to an earlier research time | `core/research/models/universe.py` | `test_future_membership_is_not_backfilled`; `test_departed_membership_is_not_silently_retained`; `test_resolver_splits_membership_transition` | VERIFIED |
| RESEARCH-RULE-013 | Genuine successor historical-retrieval failure is distinct from post-retrieval DatasetReference preparation failure | `core/research/backtest_research_orchestrator.py`; `core/research/successor_backtest_research_coordinator.py` | `test_successor_retrieval_failure_keeps_existing_incomplete_evidence_semantics`; `test_dataset_reference_persistence_failure_is_classified_as_specification_preparation`; `test_dataset_reference_catalog_failure_is_classified_as_specification_preparation` | VERIFIED |
| RESEARCH-RULE-014 | Registered Trial truth precedes registered execution and reused prior evidence preserves original execution history | `core/research/registered_study_registration.py`; `core/research/claimed_research_job_executor.py`; `core/research/sqlite_research_catalog_store.py`; `core/strategies/strategy_factory.py` | `test_register_revision_delegates_complete_population_registration`; `test_m94i1_registered_execution_ignores_mutated_resolver_strategy_alias`; `test_claimed_job_reuses_exact_accepted_execution_without_new_attempt`; `test_m94i2_corrupt_dataset_reference_blocks_supported_exact_reuse`; `test_m94i2_raw_exact_reuse_terminalizer_is_not_public_catalog_authority`; `test_m94l_raw_fresh_execution_phases_are_not_public_catalog_authority`; `test_m94m_concurrent_claimed_job_replay_executes_once`; `test_m94m_stale_internal_supplied_attempt_cannot_reexecute`; `test_m94h2_exact_reuse_rejects_missing_dataset_lineage`; `test_m94h2_exact_reuse_rejects_incompatible_dataset_lineage` | VERIFIED |
| RESEARCH-RULE-015 | Trial, ResearchJob, ExperimentSpec, RunAttempt and runtime/session identities remain distinct; retry does not inflate Trial count | `core/research/sqlite_research_catalog_store.py`; `api/research_application.py` | `test_explicit_retry_preserves_trial_spec_and_prior_failure_history`; `test_m94g4_retry_after_recovered_interrupted_bound_work_preserves_spec_and_history`; `test_duplicate_retry_request_cannot_create_second_active_job`; `test_trial_detail_exposes_durable_disposition_job_and_result_lineage`; `test_progress_response_contract_keeps_trial_and_job_counts_explicit` | VERIFIED |
| RESEARCH-RULE-016 | Durable queued ResearchJobs are claimed atomically in semantic FIFO order; cancellation/interruption/restart and authoritative pool failure remain truthful | `core/research/research_job_queue.py`; `core/research/sqlite_research_catalog_store.py`; `core/research/claimed_research_job_executor.py`; `core/research/backtest_research_orchestrator.py`; `api/main.py` | `test_claim_is_fifo_bounded_and_creates_no_attempt`; `test_m94h3_fifo_uses_exact_chronology_across_offsets_and_microseconds`; `test_m94h3_fifo_equivalent_instants_use_stable_job_id_tiebreaker`; `test_m94h2_authoritative_input_resolution_failure_propagates_fail_closed`; `test_m94h2_worker_pool_stops_after_authoritative_retrieval_failure`; `test_m94h2_worker_pool_stops_after_corrupt_prepared_manifest`; `test_m94i2_worker_pool_stops_after_unreadable_authoritative_manifest`; `test_m94g4_mixed_state_restart_recovers_only_running_work`; `test_m94l_restart_recovery_uses_attempt_creation_as_shared_terminal_floor`; `test_m94m_recovery_cannot_precede_durable_cancellation_request`; `test_worker_pool_never_exceeds_configured_worker_count` | VERIFIED |
| RESEARCH-RULE-017 | One StudyRevision owns one authoritatively proven immutable finite registered Trial population | `core/research/registered_study_registration.py`; `core/research/sqlite_research_catalog_store.py`; `core/research/research_job_queue.py` | `test_whole_revision_transaction_rolls_back_partial_population`; `test_identical_registration_is_order_independent_and_idempotent`; `test_m94i3_public_population_writer_cannot_mint_subset_proof`; `test_m94h3_standalone_revision_without_population_proof_cannot_start`; `test_m94h3_partial_private_population_without_proof_cannot_start`; `test_m94h3_authoritative_registration_persists_population_proof`; `test_m94h3_corrupt_population_proof_fails_closed_before_start`; `test_m94h3_authoritative_zero_population_is_not_startable`; M9.4g4 one-off 5,000-Trial production-registration resource measurement | VERIFIED |
| RESEARCH-RULE-018 | Continuous universe membership preserves one simulated-account episode while genuine membership gaps split episodes | `core/research/registered_study_registration.py` | `test_continuous_member_coalesces_without_snapshot_reset`; `test_true_membership_gap_creates_separate_episodes` | VERIFIED |

Exact test names and symbol-level references should be tightened whenever a row is independently audited or affected by an implementation change.

## M9.4l independent audit and M9.4m local corrective evidence

M9.4l was published/post-push verified at `d26d3d62b6e7cced738bdbf260269497e0e70d5d`. Its local validation included 176 focused tests, 207 research-only M9.4 tests across 13 modules and 1383 complete Python tests. The independent reviewer subsequently discovered 273 repository-wide M9.4 tests across 21 modules and independently ran all 1383 Python tests. The audit returned `M95_GATE=BLOCKED` with A01, A02, A03 and F03. Publication and passing tests did not establish independent acceptance.

At the 2026-10-11 pre-publication validation checkpoint, M9.4m was a local, unstaged and unpublished corrective candidate. This is a historical checkpoint statement, not an assertion about its eventual publication state. A01 adds direct canonical financial consistency checks for net/gross/cost and single-symbol close-marked equity. A02 includes durable cancellation-request time in the shared restart-recovery terminal timestamp. A03 separates public standalone prepared execution from internal supplied-RunAttempt execution and rejects stale attempts before computation; a concurrent claimed-job test verifies one physical execution through that supported entry path. Existing M4 Backtest economics, M5 WFA, M6/M7 Paper causality, M8 application authority, M9.3 data truth and the no-live-order boundary are retained.

Local M9.4m validation passed 1394 complete Python tests and 280 repository-wide M9.4 tests across 21 modules; `git diff --check` passed. At the 2026-10-11 pre-publication checkpoint, `M95_GATE=BLOCKED`. The required release sequence is final review, separately approved stage, commit and push, verification of the exact published HEAD, and a fresh independent post-publication M9.4 audit. Only an explicit `M95_GATE=PASS` for the audited published HEAD authorizes fresh M9.5 design; it does not authorize M9.5 implementation.

Existing VERIFIED traceability rows represent their cited behaviors and tests. They do not independently certify the complete M9.4m publication gate.

## M9.4m independent review and M9.4n financial-result correction

Published `6e248a2749f162738e75258d8cd972a8e037c6b4` was independently audited with `M95_GATE=BLOCKED`: B01 MEDIUM showed that hash-valid contradictory closed-trade gross profit and percentage returns reached exact reuse and Study aggregation; F03 LOW identified obsolete design introductory wording. A01/A02/A03 were independently assessed as corrected.

M9.4n updates the shared canonical result validator in `core/research/reproducibility.py` to enforce existing TradeBuilder price/quantity gross-PnL and price-return equations for closed LONG trades. Associated executable evidence includes `test_m94l_exact_reuse_rejects_additional_canonical_counterexamples`, `test_m94m_hash_valid_financial_contradictions_block_aggregation`, `test_m94m_valid_direct_financial_relationships_are_accepted`, and `test_m94n_canonical_decoder_enforces_closed_long_trade_prices`. These cases passed within the 70-test focused suite on 2026-10-11. Full Python regression subsequently passed 1403 tests and repository-wide M9.4 regression passed 287 tests across 21 modules. Independent closure remains pending; `M95_GATE=BLOCKED`.

## M9.4o independent audit and M9.4q corrective trace

M9.4q second corrective checkpoint (2026-10-14): the first M9.4q candidate corrected M94-AUD-01 by enforcing whole-share bar-record `position_size` and reconciled most M94-AUD-02 documentation. A fresh independent candidate audit then returned `M94Q_AUDIT_GATE=BLOCKED`. M94Q-AUD-01 found that hash-valid canonical results could still contain negative authoritative cash with positive whole-share holdings and pass decoding, exact reuse and Study aggregation, despite AD-018's unlevered available-cash affordability contract. M94Q-AUD-02 found the AD-025 current status stale. M94Q-AUD-03 found the required M9.4q categorical behavior-impact declaration missing. M94Q-AUD-04 found review-bundle patch/exclusion reproducibility defects; that bundle issue did not invalidate the repository-backed audit but must be repaired before the next handoff. The current committed branch HEAD remains `0f679f9c24352dea46cff965f49eb4a53f5e9eed`; the second M9.4q correction is local, unstaged and unpublished. The shared canonical Backtest-result validator now rejects `cash < 0` without normalization or tolerance, preserves exactly zero cash for fully funded whole-share holdings, and retains the whole-share `position_size` correction. Regression evidence covers real M4 canonical boundaries, direct and stable-decoder validation, hash-valid persisted exact-reuse rejection without a fabricated RunAttempt, subsequent fresh execution, and both EXECUTED and REUSED Study aggregation. Current second-correction validation passes 30 focused `m94q_` tests, 129 complete tests across the three touched modules, 333 exact repository-wide M9.4 tests across the established 21 modules, and 1457 complete Python tests; `git diff --check` is clean. The earlier 328/1451 counts remain historical evidence for the first M9.4q candidate, not current closure proof. M9.5 Gate A design remains accepted/frozen, but substantive M9.5 implementation remains blocked until the locally validated corrected candidate is separately independently reviewed, is published only through the protected Git approval gates, and the exact published HEAD receives the required independent PASS.

### M9.4q behavior-impact declaration

BEHAVIOR IMPACT: CHANGED

BEHAVIOR IDS: `BT-RULE-002`; `RESEARCH-RULE-009`; `RESEARCH-RULE-014`; `RESEARCH-RULE-004`.

BEHAVIOR BEFORE: the shared canonical Backtest-result boundary checked financial structure and, after the first M9.4q correction, whole-share `position_size`, but it could still accept a hash-valid bar record with negative authoritative cash and a positive holding when the close-marked equity equation balanced. Such a result could therefore remain eligible for exact-reuse lookup and result-bearing Study aggregation. The 2026-10-14 independent audit additionally found that hash-valid trades outside authoritative bar history could be accepted, while oversized canonical integers could propagate OverflowError instead of controlled invalid-result rejection.

BEHAVIOR AFTER: canonical Backtest-result validation rejects any bar record with `cash < 0` for the accepted unlevered research scope, without normalizing stored values or introducing a tolerance. Exactly zero cash remains valid for a fully funded whole-share holding. Whole-share `position_size`, strict neighboring quantity types, evidence identity, reuse lineage and independent-account aggregation semantics are preserved. Exact reuse and aggregation fail closed because they consume the same validated canonical result boundary. The 2026-10-15 corrective iteration additionally requires trade entry_time and any non-null exit_time to fall within the authoritative first-to-last bar timestamp interval, and converts integer overflow during finite-number validation to ValueError without normalizing stored values. Valid same-bar trades and nullable exit_time remain supported.

RATIONALE: align research-result authority with accepted AD-018/M4 economics, where available-cash affordability is the final unlevered safety boundary and an accepted long entry cannot create negative authoritative cash. The subsequent corrections prevent impossible hash-valid trade chronology from crossing canonical reuse and Study aggregation, and route oversized numeric evidence through the controlled invalid-result rejection path.

USER/RESEARCH IMPACT: impossible leveraged/borrowed canonical results cannot be accepted, reused or counted as result-bearing Study evidence while valid fully funded whole-share results remain usable. Out-of-range trade artifacts cannot be accepted as result-bearing evidence, and unrepresentable numeric artifacts no longer abort exact-reuse validation with an uncontrolled OverflowError.

IMPLEMENTATION PATHS: `core/research/reproducibility.py::validate_stable_backtest_result_payload`; executable evidence in `tests/backtest/test_m4_7_backtest_validity_integration.py`, `tests/research/test_backtest_research_orchestrator.py`, and `tests/research/test_m94f_study_aggregation.py`.

TEST/EVIDENCE: `test_m94q_real_m4_open_holding_survives_canonical_result_boundary`; `test_m94q_real_m4_same_bar_protective_exit_survives_canonical_result_boundary`; `test_m94q_zero_cash_fully_funded_whole_share_holding_is_valid`; `test_m94q_negative_cash_with_open_holding_is_rejected`; `test_m94q_stable_decoder_rejects_negative_cash_with_open_holding`; `test_m94q_negative_cash_result_is_not_reused_and_fresh_execution_remains_available`; `test_m94q_aggregation_rejects_negative_cash_for_executed_and_reused`; plus the existing fractional and neighboring-quantity M9.4q regressions. At the 2026-10-14 second-corrective checkpoint, 30 focused `m94q_` tests passed. The prior candidate then passed 129 touched-module tests, 333 M9.4 tests across 21 modules, and 1,457 full Python tests. Those broader results were independently repeated in the 2026-10-14 audit, which nevertheless returned `M94Q_AUDIT_GATE=BLOCKED` because of M94Q-NEW-01, M94Q-NEW-02 and M94Q-NEW-03. For the revised unpublished 2026-10-15 candidate, `KANASU_900147` confirmed five permanent RED cases; `KANASU_900148` confirmed five permanent GREEN cases, five reviewer-authored adversarial GREEN cases, and 35 focused `m94q_` GREEN cases. The new permanent coverage includes `test_m94q_trade_outside_bar_history_is_rejected_by_decoder`, `test_m94q_trade_outside_bar_history_is_rejected_by_aggregation`, `test_m94q_oversized_integer_is_rejected_by_direct_validator` and `test_m94q_oversized_integer_is_rejected_by_decoder`. Broader regression on this revised candidate passed at `KANASU_900150` (2026-10-15): 134 touched-module tests, 338 M9.4 tests across 21 modules, and 1,462 complete Python tests with zero failures, errors or skips. Evidence: `VALIDATION_SUMMARY.json` SHA-256 `6c5fd30e8384993ba81960f6c9b36d6431e403f30411ae62c7cfa4ba7426a04c`. At that checkpoint, a fresh independent pre-publication review remained pending. That review subsequently occurred on 2026-10-15 and returned FAIL; the corrected post-audit candidate now requires fresh independent re-review. No local regression result authorizes publication or M9.5 implementation.

UNCHANGED ADJACENT INVARIANTS: M4 execution/sizing/cost/timing/accounting code is unchanged; M5 WFA mathematics, M6/M7 Paper causality, M8 application authority, M9.2 evidence identity, M9.3 data truth, fixed Trial denominators, explicit retry/recovery semantics, no-fake-RunAttempt reuse, independent-account aggregation basis, no qualification authority in M9.4, and no live-money authority remain unchanged.

## M9.4q post-adversarial corrective traceability - 2026-10-15

| Finding | Enforced local invariant | Permanent regression evidence |
|---|---|---|
| M94Q-NEW-02 | Canonical trade and execution quantities preserve strict integer checks and reject nonfinite numeric conversion | `test_m94q_followup_trade_quantity_overflow_fails_closed` |
| M94Q-NEW-04 | Trade entry and non-null exit timestamps must match observed authoritative bar timestamps | `test_m94q_followup_trade_timestamp_requires_observed_bar` |
| M94Q-NEW-05 | Finite Study mean and median avoid the reproduced intermediate-overflow cases | `test_m94q_followup_distribution_mean_large_finite`; `test_m94q_followup_distribution_median_large_finite` |
| M94Q-NEW-06 | Fresh terminalization persists job, attempt, Trial and event timestamps no earlier than an existing durable cancellation request | `test_m94q_followup_cancel_chronology_direct`; `test_m94q_followup_cancel_chronology_claimed_executor` |

`KANASU_900168`: 348 M9.4 tests, 30 independent adversarial cases replayed,
1472 full Python tests passed; no skips or errors. Local test success is not
a fresh independent audit verdict. M9.4q remains unpublished and
`M94Q_AUDIT_GATE=BLOCKED`; substantive M9.5 implementation remains blocked.

## M9.4q FRESH-01/FRESH-02 audit-response trace - 2026-10-15

BEHAVIOR IMPACT: canonical Backtest-result validation and its evidence
fixtures; accepted M4 execution, portfolio cash ownership, long-only
scope, trial lineage, and earlier milestones remain authoritative.

BEFORE: completed trades or nonflat bars could bypass the prior flat-only
cash-constancy check. An authoritative result could therefore include
fabricated flat-account cash, unearned terminal settlement, or holdings
disappearing without supported execution.

AFTER: the shared canonical result boundary checks completed net-trade
P&L settlement at observed flat-account checkpoints, terminal flat cash
and recorded holding reductions. Nullable completed-trade exit timestamps
are not assumed to be settlement evidence by themselves: an observed exit
bar must carry compatible event, price and quantity diagnostics.

TEST/EVIDENCE: `test_m94q_final_cash_unreconciled_is_rejected`,
`test_m94q_final_cash_legitimate_accounts_stay_valid`,
`test_m94q_nullable_exit_requires_observed_settlement_evidence`,
`test_m94q_fresh_financial_phantom_execution_rejected`; KANASU_900228
(1536 full tests); KANASU_900229 (15 original independent financial cases
at five boundaries; 38 total original reviewer cases).

The earlier `M94Q-FINAL-02` documentation-drift correction was subsequently
re-reviewed by the fresh independent Codex audit on 2026-10-15. That audit
returned RED and classified the remaining documentation gap as
`M94Q-FRESH-INDEP-06` (MEDIUM): the current docs did not trace the
pre-attempt cancellation-precedence branch, its failure-metadata clearing,
the `running_cancellation_acknowledged` event, or the permanent regression
tests. Historical RED evidence remains authoritative. The local documentation
correction below addresses that specific trace gap but is not itself an
independent PASS. `M94Q_AUDIT_GATE=BLOCKED`; M9.5 implementation remains
BLOCKED.

### M9.4q FRESH-INDEP-06 pre-attempt cancellation trace - 2026-10-16

BEHAVIOR IMPACT: DOCUMENTATION ONLY. The production behavior was already
present in the current local candidate and is unchanged by this trace
correction.

BEFORE (documentation): cancellation and preparation failure were described
separately, but the docs did not state which outcome wins when a durable
cancellation request exists before an unlinked RUNNING ResearchJob reaches a
pre-attempt preparation failure.

AFTER (documented contract): `fail_running_job_without_attempt` decides the
pre-attempt terminal outcome inside the same `BEGIN IMMEDIATE` transaction
that reads durable cancellation state. For a RUNNING ResearchJob with no
RunAttempt or reuse lineage, an existing `cancel_requested_at` takes
precedence over the subsequent preparation failure. The ResearchJob and Trial
become `CANCELLED`; their failure classification and failure message are
cleared; terminal/disposition/event timestamps are no earlier than the
durable cancellation request; and the Trial-disposition event records
`running_cancellation_acknowledged`. No RunAttempt is fabricated. Without a
durable cancellation request, the same pre-attempt failure path remains
`FAILED` with the supplied failure classification and message.

SCOPE DISTINCTION: this rule is only for the unlinked pre-attempt branch. It
does not replace the established cooperative cancellation semantics for
linked/in-flight computation after RunAttempt or reuse lineage exists, and it
does not authorize force-kill, retry, resume, qualification, or live-order
behavior.

IMPLEMENTATION:
`core/research/sqlite_research_catalog_store.py::fail_running_job_without_attempt`.

TEST/EVIDENCE:
`tests/research/test_m94d_claimed_research_job_executor.py::test_m94q_fresh_cancel_pre_attempt_request_wins`;
`tests/research/test_m94d_claimed_research_job_executor.py::test_m94q_fresh_cancel_pre_attempt_no_request_stays_failure`.
`KANASU_900288` confirmed the corresponding implementation/test evidence is
present while the documentation trace was the remaining gap. This correction
does not change the historical independent FAIL or open the audit gate.

## M9.4q synchronization-review traceability - 2026-10-19

| Finding | Corrected invariant | Current executable evidence |
|---|---|---|
| `M94Q-SYNC-REVIEW-01` | Initial authoritative BarRecord cannot carry execution settlement diagnostics | fresh-independent first-bar counterexample/regression; 62/62 fresh-independent suite |
| `M94Q-SYNC-REVIEW-02` | REUSED Study lineage requires job reused-evidence identity to equal source successful RunAttempt evidence identity | `test_m94q_rereview_reused_evidence_lineage_mismatch_rejected`; 139/139 Study-aggregation module |
| `M94Q-SYNC-REVIEW-03` | Canonical Study aggregation validates immutable registered Trial population proof before denominator/statistics | `test_m94q_rereview_aggregation_rejects_registered_population_denominator_drift`; 23/23 queue/population and 139/139 aggregation modules |

Independent adversarial checks additionally pass for concurrent/idempotent
Start, duplicate-safe Retry, restart recovery without silent retry/resume,
cancellation races, exact-reuse/Study artifact authority, overflow-safe
aggregate statistics and equal independent-Trial-account weighting.

The earlier synchronization candidate passed 471/471 tests across the
explicit 14-module M9.4 focused set and 1604/1604 complete Python tests.
Those figures are historical evidence, not current corrected-candidate
validation.

Historical independent FAILs and their dated validation counts remain
historical evidence. This local synchronization checkpoint is not an
independent release PASS. `M94Q_AUDIT_GATE=BLOCKED`.

An exact-published-M9.4 independent PASS authorizes fresh M9.5 design only.
M9.5 implementation remains unauthorized until that fresh design is
separately accepted.

## M9.4q independent-review correction overlay (2026-10-19)

Fresh independent review trace additions:

| Finding | Accepted invariant | Production correction | Permanent evidence |
|---|---|---|---|
| `M94Q-IND-20261019-01` | long-only/unlevered M4 financial truth; canonical evidence/reuse authority | `core/research/reproducibility.py` requires same-bar completed-trade entry notional to be no greater than authoritative pre-bar cash with no approximate-equality overspend exception | direct validator, decoder, durable exact reuse, EXECUTED aggregation and registered REUSED rejection; strict tiny-overspend negative regression; exact-cash, fee-envelope and real-M4 positive controls |
| `M94Q-IND-20261019-02` | immutable fixed Trial denominator and truthful read models | `core/research/sqlite_research_catalog_store.py` adds connection-scoped population-proof validation; queue progress and authoritative registered-Trial reads use the same snapshot; `api/research_application.py` uses the authoritative public list read | row loss, missing proof, count-preserving identity substitution across catalog/application plus controlled HTTP failure propagation |
| `M94Q-IND-20261020-01` | immutable Trial-to-ExperimentSpec binding and truthful result-bearing lineage | `core/research/study_aggregation.py` requires the EXECUTED RunAttempt or REUSED source RunAttempt `experiment_spec_id` to equal the Trial-bound ExperimentSpec before accepting result authority | `test_m94q_independent_attempt_spec_mismatch_fails_closed`: EXECUTED/REUSED x core/application/HTTP = six permanent fail-closed cases |

A stale workflow-application test double was aligned with the new authoritative Trial-list store contract; this was test infrastructure only and did not change production semantics.

FRESH-04 checkpoint validation evidence: **545 repository-wide M9.4 tests passed across 23 files; 90 explicit preservation controls passed; 1669 complete-suite tests passed; `git diff --check` passed**. FRESH-04 targeted coverage was 4/4, FRESH-03 preservation was 18/18 and bounded regression was 256/256. These figures are historical after REVIEW-01.

Current gate after these local corrections:

- the corrections are **not published**;
- the M9.4q pre-publication gate remains **blocked pending a new fresh independent review of the exact corrected candidate**;
- staging, commit and push remain separately human-approved protected operations;
- the final M9.4 audit gate remains blocked until publication and an independent review of the exact published HEAD;
- M9.5 may begin only after that published M9.4 gate passes, and its next authority is **fresh design only**;
- M9.5 implementation is not authorized by this correction.

## M9.4q 2026-10-20 post-independent corrective trace

`M94Q-IND-20261020-01` BEHAVIOR BEFORE: an otherwise successful
result-bearing RunAttempt used by an EXECUTED Trial, or successful source
RunAttempt used by a REUSED Trial, could have its durable ExperimentSpec
foreign key substituted to another valid ExperimentSpec and Study aggregation
did not compare that attempt identity with the Trial's immutable binding.

BEHAVIOR AFTER: EXECUTED and REUSED result-bearing aggregation fails closed
unless the relevant RunAttempt's `experiment_spec_id` equals the Trial-bound
`experiment_spec_id`.

The same correction cycle closes the remaining strictness gap in
`M94Q-IND-20261019-01`: same-bar funding rejects every positive notional
overspend, including one smaller than the former reconciliation tolerance.

Permanent evidence:
`test_m94q_independent_attempt_spec_mismatch_fails_closed`
(six lineage/boundary cases) and
`test_m94q_independent_same_bar_tiny_overspend_fails_closed`.

Historical checkpoint regression: 541 repository-wide M9.4 tests across 23 files,
90 preservation controls and 1665 complete Python tests pass. This remains
local corrective evidence and not independent publication acceptance.

## M9.4q fresh independent findings trace - 2026-10-20

| Finding | Accepted invariant | Production correction | Permanent evidence |
|---|---|---|---|
| `M94Q-FRESH-20261020-01` | long-only, unlevered authoritative BUY funding | `core/research/reproducibility.py` rejects an ordinary flat-to-long BUY whenever derived entry notional is greater than authoritative pre-entry cash, before tolerant cash reconciliation | `test_m94q_fresh_ordinary_buy_tiny_overspend_fails_closed` direct/decoder negative cases; `test_m94q_fresh_ordinary_buy_exact_cash_control` direct/decoder positive cases |
| `M94Q-FRESH-20261020-02` | one observed settlement cannot establish contradictory duplicate completed-trade lineage | `core/research/reproducibility.py` uniquely consumes observed completed-trade BUY entry settlements, matching the existing fail-closed exit allocation boundary | `test_m94q_fresh_duplicate_entry_settlement_fails_closed` direct/decoder negative cases; `test_m94q_fresh_distinct_entry_settlements_control` direct/decoder positive cases |

RED evidence reproduced all four negative direct/decoder cases before the
production correction. The corrected targeted suite passed all eight
negative/positive cases. The bounded three-module regression then passed
183 tests.

At that checkpoint, broader local validation subsequently passed **541 repository-wide M9.4
tests across 23 files, 90 preservation controls and 1665 complete Python
tests**. The M4 execution engine remained byte-identical.

This trace is local remediation evidence, not independent publication
acceptance. The corrected candidate requires a new fresh independent
pre-publication review. M9.5 remains blocked.

## M9.4q FRESH-03 trace - 2026-10-20

| Finding | Accepted invariant | Production correction | Permanent evidence |
|---|---|---|---|
| `M94Q-FRESH-20261020-03` | Study aggregation may expose only a selected result actually authorized by accepted durable research evidence | `core/research/study_aggregation.py` validates EXECUTED/REUSED selected results against the authoritative RunAttempt ResearchEvidence: ACCEPTED status, ExperimentSpec dataset/configuration/repository identity, result fingerprint, and manifest/result artifact references | `tests/research/test_m94q_fresh_03_evidence_binding.py`: 16 negative + 2 positive cases; `tests/research/test_m94d_claimed_research_job_executor.py`: 6 persisted EXECUTED/REUSED core/application/HTTP cases |

The real persisted regression first produces genuine canonical result and
evidence artifacts, substitutes another genuine canonical result while
leaving accepted evidence bound to the original result, and verifies that
core Study aggregation and application aggregation fail closed and that the
real FastAPI/ASGI route returns the existing
`research_aggregation_failed` error response. The same damaged source is
also rejected by exact-reuse lookup.

The application public call contract and M4 execution engine remain unchanged.
At the FRESH-03 checkpoint, the bounded regression passed 252 tests. Broader validation passed
**541 repository-wide M9.4 tests across 23 files, 90 preservation controls
and 1665 complete Python tests**.

This is remediation evidence, not independent acceptance. The corrected
candidate remains blocked pending a fresh independent pre-publication review.

## M9.4q FRESH-04 trace - 2026-10-20

| Finding | Accepted invariant | Production correction | Permanent evidence |
|---|---|---|---|
| `M94Q-FRESH-20261020-04` | Canonical persisted Trial aggregation derives ResearchEvidence authority from the same durable database as the authoritative catalog; a foreign injected store is not an alternate authority | `core/research/study_aggregation.py` resolves evidence from `catalog_store.database_path` whenever durable catalog authority exists; explicit injection remains only for lightweight/noncanonical catalogs | `tests/research/test_m94d_claimed_research_job_executor.py`: EXECUTED + REUSED foreign-database negative cases and EXECUTED + REUSED same-database positive controls |

The permanent RED proved that canonical evidence marked non-ACCEPTED could be
bypassed by an ACCEPTED copy in a second SQLite database. The GREEN correction
rejects that authority for both EXECUTED and REUSED lineage. Default canonical
aggregation and exact-reuse rejection remain fail-closed.

At the FRESH-04 checkpoint, targeted validation passed 4 tests; FRESH-03 preservation passed
18 tests; bounded regression passed 256 tests; broad validation passed
**545 repository-wide M9.4 tests across 23 files, 90 preservation controls
and 1669 complete Python tests**.

The application public call contract and M4 execution engine remain unchanged.
The earlier **541 / 90 / 1665** figures are historical FRESH-03 checkpoint
evidence. This is local remediation evidence, not independent publication
acceptance.

## M9.4q REVIEW-01 Trial identity integrity trace - 2026-10-20

BEHAVIOR IMPACT: CHANGED at the registered-research integrity boundary only.

BEHAVIOR IDS: `RESEARCH-RULE-014`; `RESEARCH-RULE-015`;
`RESEARCH-RULE-017`.

BEHAVIOR BEFORE: the durable StudyRevision population proof validated the
registered `trial_id` denominator, but authoritative reads did not independently
prove that identity-bearing fields in each surviving persisted Trial row still
reproduced its content-addressed `trial_id`. A count-preserving mutation such as
changing `instrument_id` could therefore leave the ID-only population proof
apparently valid. Registered execution-plan resolution could reconstruct a plan
from that corrupted row.

BEHAVIOR AFTER: authoritative registered-population reads retain the accepted
population-proof format and additionally recompute each persisted Trial's
canonical `trial_id` from its registered immutable identity fields. A
contradiction fails closed. Registered execution-plan resolution crosses that
authority boundary before downstream execution-input resolution, retrieval,
RunAttempt creation or financial execution while preserving established
specific plan-validation errors.

IMPLEMENTATION PATHS:
`core/research/sqlite_research_catalog_store.py`;
`core/research/registered_trial_execution_plan.py`.

PERMANENT TEST/EVIDENCE:
`test_m94q_review_01_registered_population_read_rejects_trial_identity_corruption`;
`test_m94q_review_01_claimed_execution_rejects_trial_identity_corruption_before_retrieval`;
`test_m94q_review_01_aggregation_rejects_result_bearing_trial_identity_corruption`
for both EXECUTED and REUSED lineage.

Current validation: **4 REVIEW-01 permanent regressions; 549 repository-wide
M9.4 tests across 23 files; 90 preservation controls; 1673 complete Python
tests; clean `git diff --check`**.

Historical checkpoints remain explicit: FRESH-04 **545 / 90 / 1669** and
FRESH-03 **541 / 90 / 1665**.

UNCHANGED ADJACENT INVARIANTS: accepted M4 execution/timing/cost/accounting,
M5 WFA mathematics, M6/M7 Paper causality, M8 application authority, M9.2
reproducibility/evidence identity, M9.3 data truth, fixed Trial denominator
semantics, retry/recovery, no-fake-RunAttempt reuse, independent-account
aggregation, M9.5 qualification ownership and the no-live-money boundary.

This is local remediation evidence, not an independent PASS. The candidate is
unstaged, uncommitted and unpublished. `M94Q_AUDIT_GATE=BLOCKED` pending fresh
independent candidate review and later exact-published-HEAD independent PASS.
M9.5 implementation remains blocked.
