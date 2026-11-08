import type {
  BacktestRunRequest,
  BacktestRunResponse,
} from "@/types/backtest";
import type {
  PaperTradingStatusResponse,
} from "@/types/paperTrading";

export interface WorkspaceStudy {
  study_id: string;
  display_title: string;
  created_at: string;
  archived: boolean;
}

export interface WorkspaceQualificationPolicy {
  policy_id: string;
  version: number;
  threshold_pct: string;
}

export interface ResearchWorkspaceConfig {
  markets: Array<{ id: string; name: string }>;
  symbols: Array<{ symbol: string; exchange: string }>;
  timeframes: Array<{ id: string; label: string }>;
  strategies: Array<{ id: string; name: string }>;
  timezones: string[];
  studies: WorkspaceStudy[];
  active_qualification_policy: WorkspaceQualificationPolicy | null;
}

export interface WorkspaceBacktestRunRequest
  extends BacktestRunRequest {
  study_id: string;
}

export interface WorkspaceBacktestRunResponse
  extends BacktestRunResponse {
  attempt_id: string | null;
  evidence_id: string;
  evidence_status: "ACCEPTED" | "FAILED" | "INCOMPLETE";
  study_id: string;
  study_revision_id: string;
  trial_id: string;
}

export interface WorkspaceStrategyState {
  study_id: string;
  study_revision_id: string;
  revision_number: number;
  trial_id: string;
  instrument_id: string;
  symbol: string;
  timeframe: string;
  strategy_procedure_id: string;
  strategy_label: string;
  strategy_parameters: Record<string, unknown>;
  trial_disposition: string;
  qualification_outcome: string | null;
  qualification_decision_id: string | null;
  candidate_revision_id: string | null;
  wfa_outcome: string | null;
  wfa_verdict: "PASS" | "FAIL" | null;
  wfa_decision_id: string | null;
  paper_campaign_id: string | null;
  retryable: boolean;
}

export interface WorkspaceStrategyListResponse {
  study_id: string;
  strategies: WorkspaceStrategyState[];
}

export interface WorkspaceQualificationItem {
  trial_id: string;
  strategy_label: string;
  outcome: string;
  evidence_validity: string;
  decision_id: string | null;
  candidate_revision_id: string | null;
  decision_policy_id: string | null;
  decision_policy_version: number | null;
  decision_threshold_pct: string | null;
  reason: string;
}

export interface WorkspaceQualificationResponse {
  study_id: string;
  policy: WorkspaceQualificationPolicy;
  policy_changed: boolean;
  policy_current: boolean;
  results: WorkspaceQualificationItem[];
}

export interface WorkspaceWfaMetrics {
  consistency_ratio: number;
  avg_account_return_pct: number;
  worst_equity_drawdown_pct: number;
  stitched_total_return_pct: number;
  stitched_max_drawdown_pct: number;
  account_return_stability_score: number;
}

export interface WorkspaceWfaItem {
  trial_id: string;
  candidate_revision_id: string | null;
  strategy_label: string;
  evidence_validity: string;
  outcome: string;
  verdict: "PASS" | "FAIL" | null;
  decision_id: string | null;
  reason: string;
  metrics: WorkspaceWfaMetrics | null;
}

export interface WorkspaceWfaResponse {
  study_id: string;
  strategies: WorkspaceWfaItem[];
}

export interface WorkspacePaperSendItem {
  candidate_revision_id: string | null;
  strategy_label: string;
  outcome: string;
  campaign_id: string | null;
  reused: boolean | null;
  reason: string;
}

export interface WorkspacePaperSendResponse {
  study_id: string;
  campaigns: WorkspacePaperSendItem[];
}

export interface WorkspacePaperCampaign {
  campaign_id: string;
  study_id: string;
  study_revision_id: string;
  trial_id: string;
  candidate_revision_id: string;
  strategy_label: string;
  wfa_decision_id: string;
  created_at: string;
  current_authority: boolean;
}

export interface WorkspacePaperCampaignListResponse {
  study_id: string;
  campaigns: WorkspacePaperCampaign[];
}

export interface WorkspacePaperSession {
  session_id: string;
  state: string;
  created_at: string;
  started_at: string | null;
  terminal_at: string | null;
  failure_type: string | null;
  failure_message: string | null;
}

export interface WorkspacePaperHistory {
  campaign: WorkspacePaperCampaign;
  sessions: WorkspacePaperSession[];
  runtime: PaperTradingStatusResponse | null;
  campaign_owns_runtime: boolean;
}
