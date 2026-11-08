import { useEffect, useRef, useState } from "react";

import { ApiRequestError } from "@/api/apiClient";
import {
  getResearchWorkspaceConfig,
  getWorkspaceWfa,
  runWorkspaceWfa,
  sendWorkspaceStrategiesToPaper,
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
  WorkspacePaperSendResponse,
  WorkspaceWfaItem,
  WorkspaceWfaResponse,
} from "@/types/researchWorkspace";

function message(error: unknown, fallback: string): string {
  if (error instanceof ApiRequestError) {
    return `${error.message} (${error.code})`;
  }
  return error instanceof Error ? error.message : fallback;
}

function format(value: number): string {
  return new Intl.NumberFormat("en-IN", {
    maximumFractionDigits: 2,
  }).format(value);
}

const fixedRules = [
  "Consistency ≥ 60%",
  "Average OOS account return > 0",
  "Worst OOS equity drawdown ≤ 20%",
  "Stitched OOS return > 0",
  "Stitched maximum drawdown ≤ 20%",
  "Account-return stability ≥ 0.20",
];

export function WfaPage() {
  const [config, setConfig] =
    useState<ResearchWorkspaceConfig | null>(null);
  const [selectedStudy, setSelectedStudy] = useState("");
  const [state, setState] =
    useState<WorkspaceWfaResponse | null>(null);
  const [selectedCandidate, setSelectedCandidate] = useState("");
  const [paperResult, setPaperResult] =
    useState<WorkspacePaperSendResponse | null>(null);
  const [showRules, setShowRules] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const studyLoadSequence = useRef(0);

  async function refresh(studyId: string, sequence?: number) {
    if (!studyId) {
      setState(null);
      return;
    }
    const value = await getWorkspaceWfa(studyId);
    if (sequence !== undefined && sequence !== studyLoadSequence.current) {
      return;
    }
    setState(value);
    const first =
      value.strategies.find((item) => item.candidate_revision_id)
        ?.candidate_revision_id ?? "";
    setSelectedCandidate(first);
  }

  useEffect(() => {
    async function load() {
      try {
        const value = await getResearchWorkspaceConfig();
        setConfig(value);
        const study = value.studies[0]?.study_id ?? "";
        setSelectedStudy(study);
        if (study) {
          const sequence = ++studyLoadSequence.current;
          await refresh(study, sequence);
        }
      } catch (cause) {
        setError(message(cause, "Failed to load WFA workspace"));
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, []);

  async function handleStudyChange(studyId: string) {
    const sequence = ++studyLoadSequence.current;
    setSelectedStudy(studyId);
    setState(null);
    setSelectedCandidate("");
    setPaperResult(null);
    setShowRules(false);
    setError(null);
    try {
      await refresh(studyId, sequence);
    } catch (cause) {
      if (sequence === studyLoadSequence.current) {
        setError(message(cause, "Failed to load WFA state"));
      }
    }
  }

  async function handleRunWfa() {
    if (!selectedStudy) {
      return;
    }
    setBusy(true);
    setError(null);
    setPaperResult(null);
    const runStudy = selectedStudy;
    const runSequence = ++studyLoadSequence.current;
    try {
      const value = await runWorkspaceWfa(runStudy);
      if (
        runSequence !== studyLoadSequence.current
        || runStudy !== selectedStudy
      ) {
        return;
      }
      setState(value);
      const first =
        value.strategies.find((item) => item.candidate_revision_id)
          ?.candidate_revision_id ?? "";
      setSelectedCandidate(first);
    } catch (cause) {
      setError(message(cause, "WFA execution failed"));
    } finally {
      setBusy(false);
    }
  }

  async function handleSendToPaper() {
    if (!selectedStudy) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const sendStudy = selectedStudy;
      const value = await sendWorkspaceStrategiesToPaper(sendStudy);
      if (sendStudy === selectedStudy) {
        setPaperResult(value);
      }
    } catch (cause) {
      setError(message(cause, "Failed to send strategies to Paper"));
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <AppLayout>
        <div className="p-6">Loading WFA workspace...</div>
      </AppLayout>
    );
  }

  if (!config) {
    return (
      <AppLayout>
        <div className="p-6 text-red-400">
          {error ?? "WFA workspace unavailable"}
        </div>
      </AppLayout>
    );
  }

  const selected: WorkspaceWfaItem | undefined =
    state?.strategies.find(
      (item) => item.candidate_revision_id === selectedCandidate,
    ) ?? state?.strategies[0];

  const eligibleCount =
    state?.strategies.filter((item) => item.verdict === "PASS").length ?? 0;

  return (
    <AppLayout>
      <div className="p-6">
        <div className="mb-8">
          <div className="mb-2 text-3xl font-bold">Walk-Forward Analysis</div>
          <div className="text-slate-400">
            Run the existing candidate-bound WFA for historically eligible strategies
          </div>
        </div>

        <DashboardSection title="Study">
          <Card>
            <CardContent className="p-6">
              <div className="max-w-xl">
                <div className="mb-2 text-sm text-slate-400">Selected Study</div>
                <Select
                  value={selectedStudy}
                  onValueChange={(value) => void handleStudyChange(value)}
                  disabled={busy || config.studies.length === 0}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="No Study available" />
                  </SelectTrigger>
                  <SelectContent>
                    {config.studies.map((study) => (
                      <SelectItem key={study.study_id} value={study.study_id}>
                        {study.display_title}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="mt-5">
                <Button
                  onClick={() => void handleRunWfa()}
                  disabled={busy || !selectedStudy}
                >
                  {busy ? "Working..." : "Start WFA"}
                </Button>
              </div>
            </CardContent>
          </Card>
        </DashboardSection>

        {error ? (
          <div className="mb-6 rounded-lg border border-red-900/70 bg-red-950/30 p-3 text-sm text-red-300" role="alert">
            {error}
          </div>
        ) : null}

        <DashboardSection title="WFA Results">
          <Card>
            <CardContent className="space-y-4 p-6">
              {!state || state.strategies.length === 0 ? (
                <div className="text-slate-400">
                  No historically eligible strategies are currently available for WFA.
                </div>
              ) : (
                <>
                  <div className="space-y-2">
                    {state.strategies.map((item) => (
                      <button
                        type="button"
                        key={`${item.trial_id}-${item.decision_id ?? "operational"}`}
                        className="flex w-full items-center justify-between rounded-lg border border-slate-800 p-3 text-left hover:border-slate-600"
                        onClick={() =>
                          setSelectedCandidate(item.candidate_revision_id ?? "")
                        }
                      >
                        <span>{item.strategy_label}</span>
                        <span className="font-medium">
                          {item.outcome === "OPERATIONAL_ERROR"
                            ? "ERROR"
                            : item.verdict ?? item.outcome}
                        </span>
                      </button>
                    ))}
                  </div>

                  {selected ? (
                    <div className="rounded-lg border border-slate-800 p-4">
                      <div className="mb-3 font-semibold">
                        {selected.strategy_label}
                      </div>
                      <div className="mb-4 text-sm text-slate-400">
                        {selected.reason}
                      </div>
                      {selected.metrics ? (
                        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                          <MetricCard
                            label="Consistency"
                            value={`${format(selected.metrics.consistency_ratio * 100)}%`}
                          />
                          <MetricCard
                            label="Average OOS Return"
                            value={`${format(selected.metrics.avg_account_return_pct)}%`}
                          />
                          <MetricCard
                            label="Worst OOS Drawdown"
                            value={`${format(selected.metrics.worst_equity_drawdown_pct)}%`}
                          />
                          <MetricCard
                            label="Stitched OOS Return"
                            value={`${format(selected.metrics.stitched_total_return_pct)}%`}
                          />
                          <MetricCard
                            label="Stitched Max Drawdown"
                            value={`${format(selected.metrics.stitched_max_drawdown_pct)}%`}
                          />
                          <MetricCard
                            label="Account Return Stability"
                            value={format(selected.metrics.account_return_stability_score)}
                          />
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </>
              )}
            </CardContent>
          </Card>
        </DashboardSection>

        <DashboardSection title="Progress to Paper">
          <Card>
            <CardContent className="space-y-4 p-6">
              <div className="text-sm text-slate-400">
                Current WFA PASS strategies: {eligibleCount}
              </div>
              <Button
                variant="outline"
                disabled={busy || !selectedStudy || eligibleCount === 0}
                onClick={() => setShowRules((value) => !value)}
              >
                Send Strategies to Paper
              </Button>

              {showRules ? (
                <div className="rounded-lg border border-slate-800 p-4">
                  <div className="font-semibold">
                    Fixed WFA → Paper criteria
                  </div>
                  <div className="mt-2 text-sm text-slate-400">
                    Display only. Backend WFA PASS is authoritative.
                  </div>
                  <ul className="mt-3 space-y-1 text-sm">
                    {fixedRules.map((rule) => (
                      <li key={rule}>✓ {rule}</li>
                    ))}
                  </ul>
                  <div className="mt-4">
                    <Button
                      disabled={busy}
                      onClick={() => void handleSendToPaper()}
                    >
                      Confirm Send to Paper
                    </Button>
                  </div>
                </div>
              ) : null}

              {paperResult ? (
                <div className="space-y-2">
                  {paperResult.campaigns.length === 0 ? (
                    <div className="text-sm text-slate-400">
                      No strategies were currently eligible for Paper.
                    </div>
                  ) : (
                    paperResult.campaigns.map((item) => (
                      <div key={`${item.candidate_revision_id ?? item.strategy_label}-${item.outcome}`} className="rounded-lg border border-slate-800 p-3 text-sm">
                        <div className="font-medium">{item.strategy_label}: {item.outcome}</div>
                        <div className="text-slate-400">{item.reason}</div>
                        {item.campaign_id ? (
                          <div className="mt-1 break-all text-xs text-slate-500">Campaign: {item.campaign_id}</div>
                        ) : null}
                      </div>
                    ))
                  )}
                </div>
              ) : null}
            </CardContent>
          </Card>
        </DashboardSection>
      </div>
    </AppLayout>
  );
}
