import { apiRequest } from "@/api/apiClient";

import type {
  ResearchWorkspaceConfig,
  WorkspaceBacktestRunRequest,
  WorkspaceBacktestRunResponse,
  WorkspacePaperCampaignListResponse,
  WorkspacePaperHistory,
  WorkspacePaperSendResponse,
  WorkspaceQualificationResponse,
  WorkspaceStrategyListResponse,
  WorkspaceStrategyState,
  WorkspaceStudy,
  WorkspaceWfaResponse,
} from "@/types/researchWorkspace";

export async function getResearchWorkspaceConfig():
Promise<ResearchWorkspaceConfig> {
  return apiRequest<ResearchWorkspaceConfig>(
    "/research-workspace/config",
    undefined,
    "Failed to load research workspace",
  );
}

export async function createWorkspaceStudy(
  displayTitle: string,
): Promise<WorkspaceStudy> {
  return apiRequest<WorkspaceStudy>(
    "/research-workspace/studies",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ display_title: displayTitle }),
    },
    "Failed to create Study",
  );
}

export async function runWorkspaceBacktest(
  payload: WorkspaceBacktestRunRequest,
): Promise<WorkspaceBacktestRunResponse> {
  return apiRequest<WorkspaceBacktestRunResponse>(
    "/research-workspace/backtests/run",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    "Registered Backtest failed",
  );
}

export async function getWorkspaceStrategies(
  studyId: string,
): Promise<WorkspaceStrategyListResponse> {
  return apiRequest<WorkspaceStrategyListResponse>(
    `/research-workspace/studies/${encodeURIComponent(studyId)}/strategies`,
    undefined,
    "Failed to load saved strategies",
  );
}

export async function getWorkspaceBacktestResult(
  trialId: string,
): Promise<WorkspaceBacktestRunResponse> {
  return apiRequest<WorkspaceBacktestRunResponse>(
    `/research-workspace/trials/${encodeURIComponent(trialId)}/backtest-result`,
    undefined,
    "Failed to load saved registered Backtest result",
  );
}

export async function retryWorkspaceBacktest(
  trialId: string,
): Promise<WorkspaceStrategyState> {
  return apiRequest<WorkspaceStrategyState>(
    `/research-workspace/trials/${encodeURIComponent(trialId)}/retry`,
    { method: "POST" },
    "Registered Backtest retry failed",
  );
}

export async function qualifyWorkspaceStudy(
  studyId: string,
  thresholdPct: string,
  observedPolicyId: string | null,
): Promise<WorkspaceQualificationResponse> {
  return apiRequest<WorkspaceQualificationResponse>(
    `/research-workspace/studies/${encodeURIComponent(studyId)}/qualification`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        threshold_pct: thresholdPct,
        observed_policy_id: observedPolicyId,
      }),
    },
    "Historical qualification failed",
  );
}

export async function getWorkspaceWfa(
  studyId: string,
): Promise<WorkspaceWfaResponse> {
  return apiRequest<WorkspaceWfaResponse>(
    `/research-workspace/studies/${encodeURIComponent(studyId)}/wfa`,
    undefined,
    "Failed to load WFA state",
  );
}

export async function runWorkspaceWfa(
  studyId: string,
): Promise<WorkspaceWfaResponse> {
  return apiRequest<WorkspaceWfaResponse>(
    `/research-workspace/studies/${encodeURIComponent(studyId)}/wfa/run`,
    { method: "POST" },
    "WFA execution failed",
  );
}

export async function sendWorkspaceStrategiesToPaper(
  studyId: string,
): Promise<WorkspacePaperSendResponse> {
  return apiRequest<WorkspacePaperSendResponse>(
    `/research-workspace/studies/${encodeURIComponent(studyId)}/paper/send`,
    { method: "POST" },
    "Failed to send WFA-eligible strategies to Paper",
  );
}

export async function getWorkspacePaperCampaigns(
  studyId: string,
): Promise<WorkspacePaperCampaignListResponse> {
  return apiRequest<WorkspacePaperCampaignListResponse>(
    `/research-workspace/studies/${encodeURIComponent(studyId)}/paper`,
    undefined,
    "Failed to load Paper campaigns",
  );
}

export async function getWorkspacePaperHistory(
  campaignId: string,
): Promise<WorkspacePaperHistory> {
  return apiRequest<WorkspacePaperHistory>(
    `/research-workspace/paper-campaigns/${encodeURIComponent(campaignId)}/history`,
    undefined,
    "Failed to load Paper campaign history",
  );
}

export async function startWorkspacePaper(
  campaignId: string,
): Promise<WorkspacePaperHistory> {
  return apiRequest<WorkspacePaperHistory>(
    `/research-workspace/paper-campaigns/${encodeURIComponent(campaignId)}/start`,
    { method: "POST" },
    "Qualified Paper start failed",
  );
}

export async function stopWorkspacePaper(
  campaignId: string,
): Promise<WorkspacePaperHistory> {
  return apiRequest<WorkspacePaperHistory>(
    `/research-workspace/paper-campaigns/${encodeURIComponent(campaignId)}/stop`,
    { method: "POST" },
    "Qualified Paper stop failed",
  );
}
