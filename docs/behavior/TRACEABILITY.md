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
| RESEARCH-RULE-009 | Failed/incomplete evidence cannot become accepted reproducibility evidence | `core/research/models/research_evidence.py`; `core/research/backtest_research_orchestrator.py`; `core/research/sqlite_research_catalog_store.py` | `test_accepted_evidence_requires_all_three_fingerprints`; `test_execution_failure_creates_failed_evidence_and_failed_attempt`; `test_terminal_persistence_failure_does_not_claim_durable_success` | VERIFIED |
| RESEARCH-RULE-010 | Exact executable software identity gates ExperimentSpec/RunAttempt creation and accepted automatic evidence | `core/research/software_identity.py`; `core/research/backtest_research_orchestrator.py` | `test_clean_repository_identity_is_exact`; `test_dirty_repository_identity_is_not_exact`; `test_unknown_revision_does_not_query_worktree_status`; `test_nonexact_software_identity_never_fabricates_spec_or_attempt` | VERIFIED |
| RESEARCH-RULE-011 | Canonical instrument lineage is independent of ticker/provider identity | `core/entities/instrument.py`; `core/market_data/provider_instrument_binding.py`; `core/market_data/instrument_registry.py` | `test_binding_keeps_provider_identity_separate_from_instrument_identity`; `test_registry_preserves_effective_dated_symbol_change` | VERIFIED |
| RESEARCH-RULE-012 | Point-in-time universe evidence cannot apply a future membership state to an earlier research time | `core/research/models/universe.py` | `test_future_membership_is_not_backfilled`; `test_departed_membership_is_not_silently_retained`; `test_resolver_splits_membership_transition` | VERIFIED |
| RESEARCH-RULE-013 | Genuine successor historical-retrieval failure is distinct from post-retrieval DatasetReference preparation failure | `core/research/backtest_research_orchestrator.py`; `core/research/successor_backtest_research_coordinator.py` | `test_successor_retrieval_failure_keeps_existing_incomplete_evidence_semantics`; `test_dataset_reference_persistence_failure_is_classified_as_specification_preparation`; `test_dataset_reference_catalog_failure_is_classified_as_specification_preparation` | VERIFIED |
| RESEARCH-RULE-014 | Registered Trial truth precedes registered execution and reused prior evidence preserves original execution history | `core/research/registered_study_registration.py`; `core/research/claimed_research_job_executor.py`; `core/research/sqlite_research_catalog_store.py` | `test_register_revision_delegates_complete_population_registration`; `test_claimed_job_reuses_exact_accepted_execution_without_new_attempt`; `test_m94h2_exact_reuse_rejects_missing_dataset_lineage`; `test_m94h2_exact_reuse_rejects_incompatible_dataset_lineage`; `test_exact_reuse_rejects_evidence_missing_manifest_reference` | VERIFIED |
| RESEARCH-RULE-015 | Trial, ResearchJob, ExperimentSpec, RunAttempt and runtime/session identities remain distinct; retry does not inflate Trial count | `core/research/sqlite_research_catalog_store.py`; `api/research_application.py` | `test_explicit_retry_preserves_trial_spec_and_prior_failure_history`; `test_m94g4_retry_after_recovered_interrupted_bound_work_preserves_spec_and_history`; `test_duplicate_retry_request_cannot_create_second_active_job`; `test_trial_detail_exposes_durable_disposition_job_and_result_lineage`; `test_progress_response_contract_keeps_trial_and_job_counts_explicit` | VERIFIED |
| RESEARCH-RULE-016 | Durable queued ResearchJobs are claimed atomically in semantic FIFO order; cancellation/interruption/restart and authoritative pool failure remain truthful | `core/research/research_job_queue.py`; `core/research/sqlite_research_catalog_store.py`; `core/research/claimed_research_job_executor.py`; `api/main.py` | `test_claim_is_fifo_bounded_and_creates_no_attempt`; `test_m94h3_fifo_uses_exact_chronology_across_offsets_and_microseconds`; `test_m94h3_fifo_equivalent_instants_use_stable_job_id_tiebreaker`; `test_m94h2_authoritative_input_resolution_failure_propagates_fail_closed`; `test_m94h2_worker_pool_stops_after_authoritative_retrieval_failure`; `test_m94h2_worker_pool_stops_after_corrupt_prepared_manifest`; `test_m94g4_mixed_state_restart_recovers_only_running_work`; `test_worker_pool_never_exceeds_configured_worker_count` | VERIFIED |
| RESEARCH-RULE-017 | One StudyRevision owns one authoritatively proven immutable finite registered Trial population | `core/research/registered_study_registration.py`; `core/research/sqlite_research_catalog_store.py`; `core/research/research_job_queue.py` | `test_whole_revision_transaction_rolls_back_partial_population`; `test_identical_registration_is_order_independent_and_idempotent`; `test_m94h3_standalone_revision_without_population_proof_cannot_start`; `test_m94h3_partial_private_population_without_proof_cannot_start`; `test_m94h3_authoritative_registration_persists_population_proof`; `test_m94h3_corrupt_population_proof_fails_closed_before_start`; `test_m94h3_authoritative_zero_population_is_not_startable`; M9.4g4 one-off 5,000-Trial production-registration resource measurement | VERIFIED |
| RESEARCH-RULE-018 | Continuous universe membership preserves one simulated-account episode while genuine membership gaps split episodes | `core/research/registered_study_registration.py` | `test_continuous_member_coalesces_without_snapshot_reset`; `test_true_membership_gap_creates_separate_episodes` | VERIFIED |

Exact test names and symbol-level references should be tightened whenever a row is independently audited or affected by an implementation change.
