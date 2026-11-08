import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiRequestError } from "@/api/apiClient";
import {
  getResearchWorkspaceConfig,
  getWorkspacePaperCampaigns,
  getWorkspacePaperHistory,
  startWorkspacePaper,
  stopWorkspacePaper,
} from "@/api/researchWorkspaceApi";
import { AppLayout } from "@/app/AppLayout";
import { DashboardSection } from "@/components/dashboard/DashboardSection";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import type {
  ResearchWorkspaceConfig,
  WorkspacePaperCampaign,
  WorkspacePaperHistory,
} from "@/types/researchWorkspace";
import type { PaperTradingStatusResponse } from "@/types/paperTrading";

const POLL_MS = 2000;

function message(error: unknown, fallback: string): string {
  if (error instanceof ApiRequestError) {
    return `${error.message} (${error.code})`;
  }
  return error instanceof Error ? error.message : fallback;
}

function shouldAcceptCampaignResponse(
  requestSequence: number,
  currentSequence: number,
  requestedCampaign: string,
  currentCampaign: string,
): boolean {
  return (
    requestSequence === currentSequence
    && requestedCampaign === currentCampaign
  );
}

function format(value: number | null): string {
  if (value === null) {
    return "-";
  }
  return new Intl.NumberFormat("en-IN", {
    maximumFractionDigits: 2,
  }).format(value);
}

function RuntimeMetrics({
  status,
}: {
  status: PaperTradingStatusResponse | null;
}) {
  const snapshot = status?.snapshot;
  if (!snapshot) {
    return (
      <Card>
        <CardContent className="p-6 text-slate-400">
          No current process-local qualified Paper session.
        </CardContent>
      </Card>
    );
  }

  const metrics = [
    ["Initial Capital", format(snapshot.initial_capital)],
    ["Cash", format(snapshot.cash)],
    ["Equity", format(snapshot.equity)],
    ["Position Size", format(snapshot.position_size)],
    ["Realized PnL", format(snapshot.realized_pnl)],
    ["Unrealized PnL", format(snapshot.unrealized_pnl)],
    ["Total PnL", format(snapshot.total_pnl)],
    ["Drawdown", format(snapshot.drawdown)],
    ["Completed Trades", snapshot.completed_trade_count],
  ];

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="grid grid-cols-1 gap-4 p-6 text-sm md:grid-cols-2 xl:grid-cols-4">
          <div>
            <div className="text-slate-400">Session ID</div>
            <div className="mt-1 break-all">{snapshot.session_id}</div>
          </div>
          <div>
            <div className="text-slate-400">Status</div>
            <div className="mt-1">{snapshot.status}</div>
          </div>
          <div>
            <div className="text-slate-400">Strategy</div>
            <div className="mt-1">{snapshot.strategy_name}</div>
          </div>
          <div>
            <div className="text-slate-400">Symbol</div>
            <div className="mt-1">{snapshot.symbol}</div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {metrics.map(([label, value]) => (
          <MetricCard key={String(label)} label={String(label)} value={value} />
        ))}
      </div>

      <Card>
        <CardContent className="grid grid-cols-1 gap-4 p-6 text-sm md:grid-cols-2 xl:grid-cols-4">
          <div>
            <div className="text-slate-400">Last Execution</div>
            <div className="mt-1">{snapshot.last_execution_event ?? "-"}</div>
          </div>
          <div>
            <div className="text-slate-400">Execution Price</div>
            <div className="mt-1">{format(snapshot.last_execution_price)}</div>
          </div>
          <div>
            <div className="text-slate-400">Execution Quantity</div>
            <div className="mt-1">{snapshot.last_execution_quantity ?? "-"}</div>
          </div>
          <div>
            <div className="text-slate-400">Runtime Failure</div>
            <div className="mt-1">
              {snapshot.failure_message ?? snapshot.failure_type ?? "-"}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export function ResearchPaperPage() {
  const navigate = useNavigate();
  const [workspace, setWorkspace] =
    useState<ResearchWorkspaceConfig | null>(null);
  const [selectedStudy, setSelectedStudy] = useState("");
  const [campaigns, setCampaigns] =
    useState<WorkspacePaperCampaign[]>([]);
  const [selectedCampaign, setSelectedCampaign] = useState("");
  const [history, setHistory] =
    useState<WorkspacePaperHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pollGeneration, setPollGeneration] = useState(0);
  const studyLoadSequence = useRef(0);
  const campaignLoadSequence = useRef(0);
  const selectedCampaignRef = useRef("");

  function selectCampaign(campaignId: string) {
    selectedCampaignRef.current = campaignId;
    setSelectedCampaign(campaignId);
  }

  async function loadCampaigns(studyId: string, sequence?: number) {
    if (!studyId) {
      setCampaigns([]);
      selectCampaign("");
      setHistory(null);
      return;
    }
    const value = await getWorkspacePaperCampaigns(studyId);
    if (sequence !== undefined && sequence !== studyLoadSequence.current) {
      return;
    }
    setCampaigns(value.campaigns);
    const current =
      value.campaigns.find((item) => item.current_authority) ??
      value.campaigns[0];
    const campaignId = current?.campaign_id ?? "";
    const campaignSequence = ++campaignLoadSequence.current;
    selectCampaign(campaignId);
    if (!campaignId) {
      setHistory(null);
      return;
    }
    const historyValue = await getWorkspacePaperHistory(campaignId);
    if (
      (sequence !== undefined && sequence !== studyLoadSequence.current)
      || !shouldAcceptCampaignResponse(
        campaignSequence,
        campaignLoadSequence.current,
        campaignId,
        selectedCampaignRef.current,
      )
    ) {
      return;
    }
    setHistory(historyValue);
  }

  useEffect(() => {
    async function load() {
      try {
        const value = await getResearchWorkspaceConfig();
        setWorkspace(value);
        const study = value.studies[0]?.study_id ?? "";
        setSelectedStudy(study);
        if (study) {
          const sequence = ++studyLoadSequence.current;
          await loadCampaigns(study, sequence);
        }
      } catch (cause) {
        setError(message(cause, "Failed to load qualified Paper workspace"));
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, []);

  useEffect(() => {
    if (!history?.runtime?.active || !selectedCampaign) {
      return;
    }

    const polledCampaign = selectedCampaign;
    const selectionSequence = campaignLoadSequence.current;
    let cancelled = false;
    let timer: number | null = null;

    const schedule = () => {
      if (cancelled) {
        return;
      }
      timer = window.setTimeout(() => {
        void poll();
      }, POLL_MS);
    };

    const poll = async () => {
      try {
        const value = await getWorkspacePaperHistory(polledCampaign);
        if (
          !cancelled
          && shouldAcceptCampaignResponse(
            selectionSequence,
            campaignLoadSequence.current,
            polledCampaign,
            selectedCampaignRef.current,
          )
        ) {
          setHistory(value);
        }
      } catch (cause) {
        if (
          !cancelled
          && shouldAcceptCampaignResponse(
            selectionSequence,
            campaignLoadSequence.current,
            polledCampaign,
            selectedCampaignRef.current,
          )
        ) {
          setError(message(cause, "Qualified Paper status refresh failed"));
        }
      } finally {
        schedule();
      }
    };

    schedule();
    return () => {
      cancelled = true;
      if (timer !== null) {
        window.clearTimeout(timer);
      }
    };
  }, [history?.runtime?.active, selectedCampaign, pollGeneration]);

  async function handleStudyChange(studyId: string) {
    const sequence = ++studyLoadSequence.current;
    ++campaignLoadSequence.current;
    setSelectedStudy(studyId);
    setCampaigns([]);
    selectCampaign("");
    setHistory(null);
    setError(null);
    try {
      await loadCampaigns(studyId, sequence);
    } catch (cause) {
      if (sequence === studyLoadSequence.current) {
        setError(message(cause, "Failed to load Paper campaigns"));
      }
    }
  }

  async function handleCampaignChange(campaignId: string) {
    const sequence = ++campaignLoadSequence.current;
    selectCampaign(campaignId);
    setHistory(null);
    setError(null);
    try {
      const value = await getWorkspacePaperHistory(campaignId);
      if (sequence === campaignLoadSequence.current) {
        setHistory(value);
      }
    } catch (cause) {
      if (sequence === campaignLoadSequence.current) {
        setError(message(cause, "Failed to load campaign history"));
      }
    }
  }

  async function handleStart() {
    if (!selectedCampaign) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const campaignAtRequest = selectedCampaign;
      const selectionSequence = ++campaignLoadSequence.current;
      const value = await startWorkspacePaper(campaignAtRequest);
      if (
        shouldAcceptCampaignResponse(
          selectionSequence,
          campaignLoadSequence.current,
          campaignAtRequest,
          selectedCampaignRef.current,
        )
      ) {
        setHistory(value);
      }
    } catch (cause) {
      setError(message(cause, "Qualified Paper start failed"));
    } finally {
      setPollGeneration((value) => value + 1);
      setBusy(false);
    }
  }

  async function handleStop() {
    if (!selectedCampaign) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const campaignAtRequest = selectedCampaign;
      const selectionSequence = ++campaignLoadSequence.current;
      const value = await stopWorkspacePaper(campaignAtRequest);
      if (
        shouldAcceptCampaignResponse(
          selectionSequence,
          campaignLoadSequence.current,
          campaignAtRequest,
          selectedCampaignRef.current,
        )
      ) {
        setHistory(value);
      }
    } catch (cause) {
      setError(message(cause, "Qualified Paper stop failed"));
    } finally {
      setPollGeneration((value) => value + 1);
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <AppLayout>
        <div className="p-6">Loading qualified Paper Trading...</div>
      </AppLayout>
    );
  }

  if (!workspace) {
    return (
      <AppLayout>
        <div className="p-6 text-red-400">
          {error ?? "Qualified Paper workspace unavailable"}
        </div>
      </AppLayout>
    );
  }

  const anyRuntimeActive = history?.runtime?.active === true;
  const ownsRuntime = history?.campaign_owns_runtime === true;

  return (
    <AppLayout>
      <div className="p-6">
        <div className="mb-6">
          <div className="mb-2 text-3xl font-bold">Paper Trading</div>
          <div className="text-slate-400">
            Real market data with simulated execution
          </div>
          <div className="mt-4 flex gap-2">
            <Button>Qualified Research</Button>
            <Button
              variant="outline"
              disabled={busy || anyRuntimeActive}
              onClick={() => navigate("/paper/standalone")}
            >
              Standalone Smoke
            </Button>
          </div>
        </div>

        {error ? (
          <div className="mb-6 rounded-lg border border-red-900/70 bg-red-950/30 p-3 text-sm text-red-300" role="alert">
            {error}
          </div>
        ) : null}

        <DashboardSection title="Qualified Research">
          <Card>
            <CardContent className="space-y-4 p-6">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div>
                  <div className="mb-2 text-sm text-slate-400">Study</div>
                  <Select
                    value={selectedStudy}
                    onValueChange={(value) => void handleStudyChange(value)}
                    disabled={busy || workspace.studies.length === 0 || ownsRuntime}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="No Study available" />
                    </SelectTrigger>
                    <SelectContent>
                      {workspace.studies.map((study) => (
                        <SelectItem key={study.study_id} value={study.study_id}>
                          {study.display_title}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <div className="mb-2 text-sm text-slate-400">
                    Qualified Strategy / Campaign
                  </div>
                  <Select
                    value={selectedCampaign}
                    onValueChange={(value) => void handleCampaignChange(value)}
                    disabled={busy || campaigns.length === 0 || ownsRuntime}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Send a WFA PASS strategy first" />
                    </SelectTrigger>
                    <SelectContent>
                      {campaigns.map((campaign) => (
                        <SelectItem
                          key={campaign.campaign_id}
                          value={campaign.campaign_id}
                        >
                          {campaign.strategy_label}
                          {campaign.current_authority ? "" : " — historical"}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {history ? (
                <div className="text-sm text-slate-400">
                  WFA authority:{" "}
                  {history.campaign.current_authority
                    ? "CURRENT"
                    : "HISTORICAL / STALE"}
                  {" · "}
                  Previous sessions: {history.sessions.length}
                </div>
              ) : null}

              <div className="flex gap-2">
                <Button
                  disabled={
                    busy ||
                    !selectedCampaign ||
                    !history?.campaign.current_authority ||
                    anyRuntimeActive
                  }
                  onClick={() => void handleStart()}
                >
                  Start Paper Trading
                </Button>
                <Button
                  variant="outline"
                  disabled={busy || !anyRuntimeActive || !ownsRuntime}
                  onClick={() => void handleStop()}
                >
                  Stop Paper Trading
                </Button>
              </div>
            </CardContent>
          </Card>
        </DashboardSection>

        <DashboardSection title="Current Session">
          <RuntimeMetrics
            status={ownsRuntime ? history?.runtime ?? null : null}
          />
          {anyRuntimeActive && !ownsRuntime ? (
            <div className="mt-3 text-sm text-amber-300">
              Another Paper mode or campaign currently owns the process runtime.
            </div>
          ) : null}
        </DashboardSection>

        <DashboardSection title="Campaign History">
          <Card>
            <CardContent className="p-6">
              {!history || history.sessions.length === 0 ? (
                <div className="text-sm text-slate-400">
                  No sessions recorded for this campaign.
                </div>
              ) : (
                <div className="space-y-2">
                  {history.sessions.map((session) => (
                    <div
                      key={session.session_id}
                      className="rounded-lg border border-slate-800 p-3 text-sm"
                    >
                      <div className="font-medium">
                        {session.session_id} — {session.state}
                      </div>
                      <div className="mt-1 text-slate-400">
                        Started: {session.started_at ?? "-"} · Terminal:{" "}
                        {session.terminal_at ?? "-"}
                      </div>
                      {session.failure_message ? (
                        <div className="mt-1 text-red-300">
                          {session.failure_type ?? "Failure"}:{" "}
                          {session.failure_message}
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </DashboardSection>
      </div>
    </AppLayout>
  );
}
