import { useEffect, useRef, useState } from "react";

import { ApiRequestError } from "@/api/apiClient";
import {
  createWorkspaceStudy,
  getResearchWorkspaceConfig,
  getWorkspaceBacktestResult,
  getWorkspaceStrategies,
  qualifyWorkspaceStudy,
  retryWorkspaceBacktest,
  runWorkspaceBacktest,
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
  WorkspaceBacktestRunResponse,
  WorkspaceQualificationResponse,
  WorkspaceStrategyState,
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

function percent(value: number): string {
  return `${format(value)}%`;
}

function toRfc3339(value: string, timeZone: string): string {
  const match =
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value);
  if (!match) {
    throw new Error("Start and end must use a valid date and time");
  }
  const [, year, month, day, hour, minute] = match;
  const guess = new Date(
    Date.UTC(
      Number(year),
      Number(month) - 1,
      Number(day),
      Number(hour),
      Number(minute),
    ),
  );
  const name = new Intl.DateTimeFormat("en-US", {
    timeZone,
    timeZoneName: "longOffset",
    hour: "2-digit",
  })
    .formatToParts(guess)
    .find((part) => part.type === "timeZoneName")?.value;
  const offset =
    name === "GMT"
      ? "+00:00"
      : name && /^GMT[+-]\d{2}:\d{2}$/.test(name)
        ? name.slice(3)
        : null;
  if (!offset) {
    throw new Error(`Unable to resolve timezone ${timeZone}`);
  }
  return `${value}:00${offset}`;
}

const inputClass =
  "h-8 w-full rounded-lg border border-slate-700 bg-transparent px-2.5 text-sm outline-none focus:border-slate-500";

export function ResearchBacktestPage() {
  const [config, setConfig] =
    useState<ResearchWorkspaceConfig | null>(null);
  const [selectedStudy, setSelectedStudy] = useState("");
  const [newStudyTitle, setNewStudyTitle] = useState("");
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const [selectedTimeframe, setSelectedTimeframe] = useState("");
  const [selectedStrategy, setSelectedStrategy] = useState("");
  const [selectedTimezone, setSelectedTimezone] = useState("");
  const [startValue, setStartValue] = useState("");
  const [endValue, setEndValue] = useState("");
  const [initialCapital, setInitialCapital] = useState("100000");
  const [fastPeriod, setFastPeriod] = useState("20");
  const [slowPeriod, setSlowPeriod] = useState("50");
  const [result, setResult] =
    useState<WorkspaceBacktestRunResponse | null>(null);
  const [strategies, setStrategies] = useState<WorkspaceStrategyState[]>([]);
  const [qualification, setQualification] =
    useState<WorkspaceQualificationResponse | null>(null);
  const [threshold, setThreshold] = useState("");
  const [showQualification, setShowQualification] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const studyLoadSequence = useRef(0);

  async function refreshStrategies(studyId: string, sequence?: number) {
    if (!studyId) {
      setStrategies([]);
      return;
    }
    const state = await getWorkspaceStrategies(studyId);
    if (sequence !== undefined && sequence !== studyLoadSequence.current) {
      return;
    }
    setStrategies(state.strategies);
  }

  useEffect(() => {
    async function load() {
      try {
        const value = await getResearchWorkspaceConfig();
        setConfig(value);
        const study = value.studies[0]?.study_id ?? "";
        setSelectedStudy(study);
        setSelectedSymbol(value.symbols[0]?.symbol ?? "");
        setSelectedTimeframe(value.timeframes[0]?.id ?? "");
        setSelectedStrategy(value.strategies[0]?.id ?? "");
        setSelectedTimezone(value.timezones[0] ?? "");
        setThreshold(
          value.active_qualification_policy?.threshold_pct ?? "",
        );
        if (study) {
          const sequence = ++studyLoadSequence.current;
          await refreshStrategies(study, sequence);
        }
      } catch (cause) {
        setError(message(cause, "Failed to load research workspace"));
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, []);

  async function handleCreateStudy() {
    const title = newStudyTitle.trim();
    if (!title) {
      setError("Enter a Study name");
      return;
    }
    const sequence = ++studyLoadSequence.current;
    setBusy(true);
    setError(null);
    try {
      const study = await createWorkspaceStudy(title);
      const value = await getResearchWorkspaceConfig();
      if (sequence !== studyLoadSequence.current) {
        return;
      }
      setConfig(value);
      setSelectedStudy(study.study_id);
      setNewStudyTitle("");
      setStrategies([]);
      setResult(null);
      setQualification(null);
    } catch (cause) {
      setError(message(cause, "Failed to create Study"));
    } finally {
      setBusy(false);
    }
  }

  async function handleStudyChange(studyId: string) {
    const sequence = ++studyLoadSequence.current;
    setSelectedStudy(studyId);
    setStrategies([]);
    setResult(null);
    setQualification(null);
    setShowQualification(false);
    setError(null);
    try {
      await refreshStrategies(studyId, sequence);
    } catch (cause) {
      if (sequence === studyLoadSequence.current) {
        setError(message(cause, "Failed to load Study strategies"));
      }
    }
  }

  async function handleRun() {
    setError(null);
    const capital = Number(initialCapital);
    const fast = Number(fastPeriod);
    const slow = Number(slowPeriod);
    if (
      !selectedStudy ||
      !selectedSymbol ||
      !selectedTimeframe ||
      !selectedStrategy ||
      !selectedTimezone ||
      !startValue ||
      !endValue
    ) {
      setError("Select a Study and complete all Backtest inputs");
      return;
    }
    if (!Number.isFinite(capital) || capital <= 0) {
      setError("Initial capital must be greater than zero");
      return;
    }
    if (
      !Number.isInteger(fast) ||
      !Number.isInteger(slow) ||
      fast <= 0 ||
      slow <= 0 ||
      fast >= slow
    ) {
      setError("SMA periods must be positive integers with fast < slow");
      return;
    }
    try {
      const start = toRfc3339(startValue, selectedTimezone);
      const end = toRfc3339(endValue, selectedTimezone);
      if (Date.parse(end) <= Date.parse(start)) {
        setError("End must be after start");
        return;
      }
      const runStudy = selectedStudy;
      const sequence = ++studyLoadSequence.current;
      setBusy(true);
      setResult(null);
      const value = await runWorkspaceBacktest({
        study_id: runStudy,
        symbol: selectedSymbol,
        timeframe: selectedTimeframe,
        strategy_id: selectedStrategy,
        start,
        end,
        timezone: selectedTimezone,
        initial_capital: capital,
        strategy_params: {
          fast_period: fast,
          slow_period: slow,
        },
      });
      if (sequence === studyLoadSequence.current) {
        setResult(value);
        await refreshStrategies(runStudy, sequence);
      }
    } catch (cause) {
      setError(message(cause, "Registered Backtest failed"));
    } finally {
      setBusy(false);
    }
  }

  async function handleOpenResult(trialId: string) {
    const studyAtRequest = selectedStudy;
    setBusy(true);
    setError(null);
    try {
      const value = await getWorkspaceBacktestResult(trialId);
      if (studyAtRequest === selectedStudy && value.study_id === selectedStudy) {
        setResult(value);
      }
    } catch (cause) {
      setError(message(cause, "Saved Backtest result could not be loaded"));
    } finally {
      setBusy(false);
    }
  }

  async function handleRetry(trialId: string) {
    const retryStudy = selectedStudy;
    const sequence = ++studyLoadSequence.current;
    setBusy(true);
    setError(null);
    try {
      await retryWorkspaceBacktest(trialId);
      await refreshStrategies(retryStudy, sequence);
    } catch (cause) {
      setError(message(cause, "Backtest retry failed"));
    } finally {
      setBusy(false);
    }
  }

  async function handleQualification() {
    if (!selectedStudy || !threshold.trim()) {
      setError("Enter the profitable-trade-rate threshold");
      return;
    }
    const numeric = Number(threshold);
    if (!Number.isFinite(numeric) || numeric < 0 || numeric > 100) {
      setError("Qualification threshold must be between 0 and 100");
      return;
    }
    const qualificationStudy = selectedStudy;
    const sequence = ++studyLoadSequence.current;
    const observedPolicyId =
      config?.active_qualification_policy?.policy_id ?? null;
    setBusy(true);
    setError(null);
    try {
      const value = await qualifyWorkspaceStudy(
        qualificationStudy,
        threshold.trim(),
        observedPolicyId,
      );
      if (sequence === studyLoadSequence.current) {
        setQualification(value);
        setThreshold(value.policy.threshold_pct);
        if (value.policy_current) {
          setConfig((current) =>
            current
              ? {
                  ...current,
                  active_qualification_policy: value.policy,
                }
              : current,
          );
        }
        await refreshStrategies(qualificationStudy, sequence);
      }
    } catch (cause) {
      if (
        cause instanceof ApiRequestError
        && cause.status === 409
        && cause.code === "qualification_policy_conflict"
      ) {
        try {
          const refreshed = await getResearchWorkspaceConfig();
          setConfig(refreshed);
          setQualification(null);
          setError(
            "Global qualification policy changed since this page loaded. "
              + "Review the current-policy warning and submit again.",
          );
        } catch (refreshCause) {
          setError(
            message(
              refreshCause,
              "Global qualification policy changed and current policy could not be refreshed",
            ),
          );
        }
      } else {
        setError(message(cause, "Historical qualification failed"));
      }
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <AppLayout>
        <div className="p-6">Loading research workspace...</div>
      </AppLayout>
    );
  }

  if (!config) {
    return (
      <AppLayout>
        <div className="p-6 text-red-400">
          {error ?? "Research workspace unavailable"}
        </div>
      </AppLayout>
    );
  }

  const activeThreshold =
    config.active_qualification_policy?.threshold_pct ?? null;
  const thresholdChanged =
    activeThreshold !== null &&
    threshold.trim() !== "" &&
    Number(threshold) !== Number(activeThreshold);

  const metrics = result
    ? [
        ["Completed Trades", result.summary.completed_trade_count],
        ["Profitable Trades", result.summary.net_profitable_trade_count],
        ["Losing Trades", result.summary.net_losing_trade_count],
        ["Breakeven Trades", result.summary.net_breakeven_trade_count],
        ["Profitable Trade Rate", percent(result.summary.net_profitable_trade_rate_pct)],
        ["Mean Positive Return", percent(result.summary.mean_positive_instrument_return_pct)],
        ["Mean Negative Return", percent(result.summary.mean_negative_instrument_return_pct)],
        ["Mean Instrument Return", percent(result.summary.mean_instrument_return_pct)],
        ["Gross Realized PnL", format(result.summary.gross_realized_pnl)],
        ["Net Realized PnL", format(result.summary.net_realized_pnl)],
        ["Mean Net PnL / Trade", format(result.summary.mean_net_pnl_per_completed_trade)],
        ["Transaction Costs", format(result.summary.completed_trade_transaction_cost_total)],
        ["Account PnL", format(result.summary.account_pnl)],
        ["Account Return", percent(result.summary.account_return_pct)],
        ["Max Equity Drawdown", percent(result.summary.max_equity_drawdown_pct)],
      ]
    : [];

  return (
    <AppLayout>
      <div className="p-6">
        <div className="mb-8">
          <div className="mb-2 text-3xl font-bold">Backtest Workspace</div>
          <div className="text-slate-400">
            Registered research Backtest with durable Study lineage
          </div>
        </div>

        <DashboardSection title="Study">
          <Card>
            <CardContent className="space-y-4 p-6">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div>
                  <div className="mb-2 text-sm text-slate-400">Selected Study</div>
                  <Select
                    value={selectedStudy}
                    onValueChange={(value) => void handleStudyChange(value)}
                    disabled={busy || config.studies.length === 0}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Create a Study first" />
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
                <div>
                  <label className="mb-2 block text-sm text-slate-400" htmlFor="new-study">
                    New Study
                  </label>
                  <div className="flex gap-2">
                    <input
                      id="new-study"
                      className={inputClass}
                      value={newStudyTitle}
                      onChange={(event) => setNewStudyTitle(event.target.value)}
                      placeholder="e.g. SMA Swing Research"
                    />
                    <Button
                      variant="outline"
                      disabled={busy}
                      onClick={() => void handleCreateStudy()}
                    >
                      Create
                    </Button>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </DashboardSection>

        <DashboardSection title="Configuration">
          <Card>
            <CardContent className="p-6">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                <div>
                  <div className="mb-2 text-sm text-slate-400">Symbol</div>
                  <Select value={selectedSymbol} onValueChange={setSelectedSymbol}>
                    <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {config.symbols.map((item) => (
                        <SelectItem key={`${item.exchange}-${item.symbol}`} value={item.symbol}>
                          {item.symbol}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <div className="mb-2 text-sm text-slate-400">Timeframe</div>
                  <Select value={selectedTimeframe} onValueChange={setSelectedTimeframe}>
                    <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {config.timeframes.map((item) => (
                        <SelectItem key={item.id} value={item.id}>{item.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <div className="mb-2 text-sm text-slate-400">Strategy</div>
                  <Select value={selectedStrategy} onValueChange={setSelectedStrategy}>
                    <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {config.strategies.map((item) => (
                        <SelectItem key={item.id} value={item.id}>{item.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <div className="mb-2 text-sm text-slate-400">Timezone</div>
                  <Select value={selectedTimezone} onValueChange={setSelectedTimezone}>
                    <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {config.timezones.map((item) => (
                        <SelectItem key={item} value={item}>{item}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <label className="text-sm text-slate-400">
                  Start
                  <input
                    aria-label="Backtest start"
                    type="datetime-local"
                    className={`${inputClass} mt-2`}
                    value={startValue}
                    onChange={(event) => setStartValue(event.target.value)}
                  />
                </label>
                <label className="text-sm text-slate-400">
                  End
                  <input
                    aria-label="Backtest end"
                    type="datetime-local"
                    className={`${inputClass} mt-2`}
                    value={endValue}
                    onChange={(event) => setEndValue(event.target.value)}
                  />
                </label>
                <label className="text-sm text-slate-400">
                  Initial Capital
                  <input
                    aria-label="Initial capital"
                    type="number"
                    className={`${inputClass} mt-2`}
                    value={initialCapital}
                    onChange={(event) => setInitialCapital(event.target.value)}
                  />
                </label>
                <label className="text-sm text-slate-400">
                  SMA Fast Period
                  <input
                    aria-label="SMA fast period"
                    type="number"
                    className={`${inputClass} mt-2`}
                    value={fastPeriod}
                    onChange={(event) => setFastPeriod(event.target.value)}
                  />
                </label>
                <label className="text-sm text-slate-400">
                  SMA Slow Period
                  <input
                    aria-label="SMA slow period"
                    type="number"
                    className={`${inputClass} mt-2`}
                    value={slowPeriod}
                    onChange={(event) => setSlowPeriod(event.target.value)}
                  />
                </label>
              </div>
              <div className="mt-6">
                <Button
                  onClick={() => void handleRun()}
                  disabled={busy || !selectedStudy}
                >
                  {busy ? "Working..." : "Start Backtest"}
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

        <DashboardSection title="Results">
          {!result ? (
            <Card>
              <CardContent className="p-6 text-slate-400">
                Start a registered Backtest to view authoritative results.
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-6">
              <Card>
                <CardContent className="grid grid-cols-1 gap-4 p-6 text-sm md:grid-cols-2 xl:grid-cols-4">
                  <div><div className="text-slate-400">Run ID</div><div className="mt-1 break-all">{result.run_id}</div></div>
                  <div><div className="text-slate-400">Status</div><div className="mt-1">{result.status}</div></div>
                  <div><div className="text-slate-400">Symbol / Timeframe</div><div className="mt-1">{result.symbol} / {result.timeframe}</div></div>
                  <div><div className="text-slate-400">Strategy</div><div className="mt-1">{result.strategy_id}</div></div>
                  <div><div className="text-slate-400">Start</div><div className="mt-1">{result.start}</div></div>
                  <div><div className="text-slate-400">End</div><div className="mt-1">{result.end}</div></div>
                  <div><div className="text-slate-400">Timezone</div><div className="mt-1">{result.timezone}</div></div>
                  <div><div className="text-slate-400">Evidence</div><div className="mt-1">{result.evidence_status}</div></div>
                  <div><div className="text-slate-400">Study Revision</div><div className="mt-1 break-all">{result.study_revision_id}</div></div>
                  <div><div className="text-slate-400">Trial</div><div className="mt-1 break-all">{result.trial_id}</div></div>
                </CardContent>
              </Card>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {metrics.map(([label, value]) => (
                  <MetricCard key={String(label)} label={String(label)} value={value} />
                ))}
              </div>
              <Card>
                <CardContent className="p-6">
                  <div className="mb-3 font-semibold">Equity Curve</div>
                  <div className="max-h-72 overflow-auto">
                    <table className="w-full text-left text-sm">
                      <thead><tr className="border-b border-slate-800 text-slate-400"><th className="p-2">Timestamp</th><th className="p-2 text-right">Equity</th></tr></thead>
                      <tbody>
                        {result.equity_curve.map((point) => (
                          <tr key={point.timestamp} className="border-b border-slate-900">
                            <td className="p-2">{point.timestamp}</td>
                            <td className="p-2 text-right">{format(point.equity)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-6">
                  <div className="mb-3 font-semibold">Completed Trades</div>
                  <div className="max-h-80 overflow-auto">
                    <table className="w-full min-w-[900px] text-left text-sm">
                      <thead>
                        <tr className="border-b border-slate-800 text-slate-400">
                          <th className="p-2">Symbol</th>
                          <th className="p-2">Direction</th>
                          <th className="p-2">Entry</th>
                          <th className="p-2 text-right">Entry Price</th>
                          <th className="p-2">Exit</th>
                          <th className="p-2 text-right">Exit Price</th>
                          <th className="p-2 text-right">Stop</th>
                          <th className="p-2 text-right">Qty</th>
                          <th className="p-2">Exit Reason</th>
                          <th className="p-2 text-right">Gross PnL</th>
                          <th className="p-2 text-right">Costs</th>
                          <th className="p-2 text-right">Net PnL</th>
                          <th className="p-2 text-right">Return</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.trades.map((trade, index) => (
                          <tr key={`${trade.entry_time}-${index}`} className="border-b border-slate-900">
                            <td className="p-2">{trade.symbol}</td>
                            <td className="p-2">{trade.direction}</td>
                            <td className="p-2">{trade.entry_time}</td>
                            <td className="p-2 text-right">{format(trade.entry_price)}</td>
                            <td className="p-2">{trade.exit_time}</td>
                            <td className="p-2 text-right">{format(trade.exit_price)}</td>
                            <td className="p-2 text-right">{format(trade.stop_price)}</td>
                            <td className="p-2 text-right">{trade.quantity}</td>
                            <td className="p-2">{trade.exit_reason}</td>
                            <td className="p-2 text-right">{format(trade.gross_pnl)}</td>
                            <td className="p-2 text-right">{format(trade.transaction_cost)}</td>
                            <td className="p-2 text-right">{format(trade.net_pnl)}</td>
                            <td className="p-2 text-right">{percent(trade.instrument_return_pct)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </DashboardSection>

        <DashboardSection title="Saved Strategies">
          <Card>
            <CardContent className="space-y-4 p-6">
              {strategies.length === 0 ? (
                <div className="text-sm text-slate-400">
                  No registered Backtests in this Study yet.
                </div>
              ) : (
                <div className="space-y-2">
                  {strategies.map((item) => (
                    <div key={item.trial_id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-800 p-3 text-sm">
                      <div>
                        <div className="font-medium">{item.symbol} — {item.strategy_label}</div>
                        <div className="text-slate-400">
                          Backtest {item.trial_disposition}
                          {item.qualification_outcome ? ` · Qualification ${item.qualification_outcome}` : ""}
                          {item.wfa_verdict ? ` · WFA ${item.wfa_verdict}` : ""}
                        </div>
                      </div>
                      <div className="flex gap-2">
                        {item.trial_disposition === "EXECUTED" || item.trial_disposition === "REUSED" ? (
                          <Button variant="outline" disabled={busy} onClick={() => void handleOpenResult(item.trial_id)}>
                            Open Result
                          </Button>
                        ) : null}
                        {item.retryable ? (
                          <Button variant="outline" disabled={busy} onClick={() => void handleRetry(item.trial_id)}>
                            Retry Backtest
                          </Button>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div>
                <Button
                  variant="outline"
                  disabled={!selectedStudy || strategies.length === 0 || busy}
                  onClick={() => setShowQualification((value) => !value)}
                >
                  Send Strategies to WFA
                </Button>
              </div>

              {showQualification ? (
                <div className="rounded-lg border border-slate-800 p-4">
                  <div className="font-semibold">Historical Qualification</div>
                  <label className="mt-3 block text-sm text-slate-400">
                    Profitable Trade Rate ≥
                    <div className="mt-2 flex max-w-xs items-center gap-2">
                      <input
                        aria-label="Qualification threshold"
                        type="number"
                        min="0"
                        max="100"
                        step="any"
                        className={inputClass}
                        value={threshold}
                        onChange={(event) => setThreshold(event.target.value)}
                      />
                      <span>%</span>
                    </div>
                  </label>
                  {activeThreshold === null ? (
                    <div className="mt-3 text-sm text-amber-300">
                      No active global qualification policy exists. Submitting this threshold creates and activates Version 1.
                    </div>
                  ) : thresholdChanged ? (
                    <div className="mt-3 text-sm text-amber-300">
                      Changing the global threshold from {activeThreshold}% to {threshold}% creates a new policy version. Previous-policy eligibility becomes historical.
                    </div>
                  ) : (
                    <div className="mt-3 text-sm text-slate-400">
                      Current global policy threshold: {activeThreshold}%.
                    </div>
                  )}
                  <div className="mt-4">
                    <Button disabled={busy || !threshold.trim()} onClick={() => void handleQualification()}>
                      Apply and Send
                    </Button>
                  </div>
                </div>
              ) : null}

              {qualification ? (
                <div className="space-y-2">
                  {!qualification.policy_current ? (
                    <div className="rounded-lg border border-amber-800/70 bg-amber-950/20 p-3 text-sm text-amber-200">
                      This qualification policy was superseded by another concurrent global policy change. Results below remain truthful historical decisions; rerun qualification to establish current eligibility.
                    </div>
                  ) : null}
                  {qualification.results.map((item) => (
                    <div key={`${item.trial_id}-${item.decision_id ?? "error"}`} className="rounded-lg border border-slate-800 p-3 text-sm">
                      <div className="font-medium">{item.strategy_label}: {item.outcome}</div>
                      <div className="mt-1 text-slate-400">{item.reason}</div>
                      {item.decision_threshold_pct ? (
                        <div className="mt-1 text-xs text-slate-500">Decision threshold: {item.decision_threshold_pct}%</div>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : null}
            </CardContent>
          </Card>
        </DashboardSection>
      </div>
    </AppLayout>
  );
}
