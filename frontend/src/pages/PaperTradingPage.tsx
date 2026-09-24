import { useEffect, useState } from "react";

import { ApiRequestError } from "@/api/apiClient";
import {
  getPaperTradingConfig,
  getPaperTradingStatus,
  startPaperTrading,
  stopPaperTrading,
} from "@/api/paperTradingApi";
import { AppLayout } from "@/app/AppLayout";
import { DashboardSection } from "@/components/dashboard/DashboardSection";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import type {
  PaperTradingConfigResponse,
  PaperTradingSnapshot,
  PaperTradingStatusResponse,
} from "@/types/paperTrading";

const POLL_INTERVAL_MS = 2000;

function formatNumber(
  value: number | null,
): string {
  if (value === null) {
    return "-";
  }

  return new Intl.NumberFormat(
    "en-IN",
    {
      maximumFractionDigits: 2,
    },
  ).format(value);
}

function errorMessage(
  error: unknown,
  fallback: string,
): string {
  if (error instanceof ApiRequestError) {
    return `${error.message} (${error.code})`;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return fallback;
}

function statusFromSnapshot(
  snapshot: PaperTradingSnapshot,
): PaperTradingStatusResponse {
  return {
    active:
      snapshot.status === "CREATED" ||
      snapshot.status === "RUNNING",
    snapshot,
  };
}

function SnapshotField({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div>
      <div className="text-sm text-slate-400">
        {label}
      </div>

      <div className="mt-1 break-words font-medium">
        {value}
      </div>
    </div>
  );
}

function AccountMetrics({
  snapshot,
}: {
  snapshot: PaperTradingSnapshot;
}) {
  const metrics = [
    {
      label: "Initial Capital",
      value: formatNumber(
        snapshot.initial_capital,
      ),
    },
    {
      label: "Cash",
      value: formatNumber(
        snapshot.cash,
      ),
    },
    {
      label: "Position Size",
      value: formatNumber(
        snapshot.position_size,
      ),
    },
    {
      label: "Position Value",
      value: formatNumber(
        snapshot.position_value,
      ),
    },
    {
      label: "Equity",
      value: formatNumber(
        snapshot.equity,
      ),
    },
    {
      label: "Realized PnL",
      value: formatNumber(
        snapshot.realized_pnl,
      ),
    },
    {
      label: "Unrealized PnL",
      value: formatNumber(
        snapshot.unrealized_pnl,
      ),
    },
    {
      label: "Total PnL",
      value: formatNumber(
        snapshot.total_pnl,
      ),
    },
    {
      label: "Peak Equity",
      value: formatNumber(
        snapshot.peak_equity,
      ),
    },
    {
      label: "Drawdown",
      value: formatNumber(
        snapshot.drawdown,
      ),
    },
    {
      label: "Completed Trades",
      value:
        snapshot.completed_trade_count,
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {metrics.map((metric) => (
        <MetricCard
          key={metric.label}
          label={metric.label}
          value={metric.value}
        />
      ))}
    </div>
  );
}

export function PaperTradingPage() {
  const [
    config,
    setConfig,
  ] =
    useState<PaperTradingConfigResponse | null>(
      null,
    );

  const [
    statusResponse,
    setStatusResponse,
  ] =
    useState<PaperTradingStatusResponse | null>(
      null,
    );

  const [loading, setLoading] =
    useState(true);

  const [
    configError,
    setConfigError,
  ] =
    useState<string | null>(null);

  const [
    actionError,
    setActionError,
  ] =
    useState<string | null>(null);

  const [
    refreshError,
    setRefreshError,
  ] =
    useState<string | null>(null);

  const [
    selectedStrategy,
    setSelectedStrategy,
  ] = useState("");

  const [
    selectedSymbol,
    setSelectedSymbol,
  ] = useState("");

  const [isStarting, setIsStarting] =
    useState(false);

  const [isStopping, setIsStopping] =
    useState(false);

  const [
    isRefreshing,
    setIsRefreshing,
  ] = useState(false);

  const isActive =
    statusResponse?.active === true;

  const snapshot =
    statusResponse?.snapshot ?? null;

  useEffect(() => {
    let cancelled = false;

    async function loadApplicationState() {
      try {
        const configResult =
          await getPaperTradingConfig();

        if (cancelled) {
          return;
        }

        setConfig(configResult);

        setSelectedStrategy(
          configResult.strategies[0]?.id ??
            "",
        );

        setSelectedSymbol(
          configResult.symbols[0]?.symbol ??
            "",
        );

        try {
          const statusResult =
            await getPaperTradingStatus();

          if (!cancelled) {
            setStatusResponse(statusResult);
          }
        } catch (error) {
          if (!cancelled) {
            setRefreshError(
              errorMessage(
                error,
                "Failed to load paper trading status",
              ),
            );
          }
        }
      } catch (error) {
        if (!cancelled) {
          setConfigError(
            errorMessage(
              error,
              "Failed to load paper trading configuration",
            ),
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadApplicationState();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!isActive) {
      return;
    }

    let cancelled = false;
    let timeoutId: number | null = null;

    const scheduleNext = () => {
      if (!cancelled) {
        timeoutId = window.setTimeout(
          pollStatus,
          POLL_INTERVAL_MS,
        );
      }
    };

    async function pollStatus() {
      try {
        const status =
          await getPaperTradingStatus();

        if (cancelled) {
          return;
        }

        setStatusResponse(status);
        setRefreshError(null);

        if (status.active) {
          scheduleNext();
        }
      } catch (error) {
        if (cancelled) {
          return;
        }

        setRefreshError(
          errorMessage(
            error,
            "Failed to refresh paper trading status",
          ),
        );

        scheduleNext();
      }
    }

    scheduleNext();

    return () => {
      cancelled = true;

      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [isActive]);

  async function handleRefreshStatus() {
    setIsRefreshing(true);
    setRefreshError(null);

    try {
      const status =
        await getPaperTradingStatus();

      setStatusResponse(status);
    } catch (error) {
      setRefreshError(
        errorMessage(
          error,
          "Failed to refresh paper trading status",
        ),
      );
    } finally {
      setIsRefreshing(false);
    }
  }

  async function handleStartPaperTrading() {
    setActionError(null);
    setRefreshError(null);

    if (
      !selectedSymbol ||
      !selectedStrategy
    ) {
      setActionError(
        "Select a symbol and strategy",
      );
      return;
    }

    setIsStarting(true);

    let startSnapshot: PaperTradingSnapshot;

    try {
      startSnapshot =
        await startPaperTrading({
          symbol: selectedSymbol,
          strategy_id: selectedStrategy,
        });
    } catch (error) {
      setActionError(
        errorMessage(
          error,
          "Paper trading start failed",
        ),
      );

      setIsStarting(false);
      return;
    }

    try {
      const status =
        await getPaperTradingStatus();

      setStatusResponse(status);
    } catch (error) {
      setStatusResponse(
        statusFromSnapshot(startSnapshot),
      );

      setRefreshError(
        errorMessage(
          error,
          "Paper trading started, but current status could not be loaded",
        ),
      );
    } finally {
      setIsStarting(false);
    }
  }

  async function handleStopPaperTrading() {
    setActionError(null);
    setRefreshError(null);
    setIsStopping(true);

    let stopSnapshot: PaperTradingSnapshot;

    try {
      stopSnapshot =
        await stopPaperTrading();
    } catch (error) {
      setActionError(
        errorMessage(
          error,
          "Paper trading stop failed",
        ),
      );

      setIsStopping(false);
      return;
    }

    try {
      const status =
        await getPaperTradingStatus();

      setStatusResponse(status);
    } catch (error) {
      setStatusResponse(
        statusFromSnapshot(stopSnapshot),
      );

      setRefreshError(
        errorMessage(
          error,
          "Paper trading stopped, but terminal status could not be loaded",
        ),
      );
    } finally {
      setIsStopping(false);
    }
  }

  if (loading) {
    return (
      <AppLayout>
        <div className="p-6">
          Loading paper trading application
          state...
        </div>
      </AppLayout>
    );
  }

  if (configError || !config) {
    return (
      <AppLayout>
        <div className="p-6 text-red-400">
          {configError ??
            "Paper trading configuration unavailable"}
        </div>
      </AppLayout>
    );
  }

  const controlsBusy =
    isStarting ||
    isStopping ||
    isRefreshing;

  const canStart =
    statusResponse !== null &&
    !statusResponse.active &&
    Boolean(
      selectedSymbol &&
        selectedStrategy,
    ) &&
    !controlsBusy;

  const canStop =
    statusResponse?.active === true &&
    !controlsBusy;

  return (
    <AppLayout>
      <div className="p-6">
        <div className="mb-8">
          <div className="mb-2 text-3xl font-bold">
            Paper Trading Runtime
          </div>

          <div className="text-slate-400">
            Monitor and control the
            authoritative paper trading
            session
          </div>
        </div>

        <DashboardSection title="Configuration">
          <Card>
            <CardContent className="p-6">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div>
                  <div className="mb-2 text-sm text-slate-400">
                    Strategy
                  </div>

                  <Select
                    value={selectedStrategy}
                    onValueChange={
                      setSelectedStrategy
                    }
                    disabled={
                      isActive ||
                      controlsBusy
                    }
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>

                    <SelectContent>
                      {config.strategies.map(
                        (strategy) => (
                          <SelectItem
                            key={
                              strategy.id
                            }
                            value={
                              strategy.id
                            }
                          >
                            {
                              strategy.name
                            }
                          </SelectItem>
                        ),
                      )}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <div className="mb-2 text-sm text-slate-400">
                    Symbol
                  </div>

                  <Select
                    value={selectedSymbol}
                    onValueChange={
                      setSelectedSymbol
                    }
                    disabled={
                      isActive ||
                      controlsBusy
                    }
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>

                    <SelectContent>
                      {config.symbols.map(
                        (symbol) => (
                          <SelectItem
                            key={
                              symbol.symbol
                            }
                            value={
                              symbol.symbol
                            }
                          >
                            {
                              symbol.symbol
                            }
                          </SelectItem>
                        ),
                      )}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {actionError ? (
                <div
                  className="mt-5 rounded-lg border border-red-900/70 bg-red-950/30 p-3 text-sm text-red-300"
                  role="alert"
                >
                  {actionError}
                </div>
              ) : null}

              {refreshError ? (
                <div
                  className="mt-5 rounded-lg border border-amber-900/70 bg-amber-950/30 p-3 text-sm text-amber-300"
                  role="status"
                >
                  {refreshError}
                </div>
              ) : null}

              <div className="mt-6 flex flex-wrap gap-3">
                <Button
                  onClick={
                    handleStartPaperTrading
                  }
                  disabled={!canStart}
                >
                  {isStarting
                    ? "Starting..."
                    : "Start Paper Trading"}
                </Button>

                <Button
                  variant="outline"
                  onClick={
                    handleStopPaperTrading
                  }
                  disabled={!canStop}
                >
                  {isStopping
                    ? "Stopping..."
                    : "Stop Session"}
                </Button>

                <Button
                  variant="outline"
                  onClick={
                    handleRefreshStatus
                  }
                  disabled={controlsBusy}
                >
                  {isRefreshing
                    ? "Refreshing..."
                    : "Refresh Status"}
                </Button>
              </div>
            </CardContent>
          </Card>
        </DashboardSection>

        <DashboardSection title="Session Status">
          <Card>
            <CardContent className="p-6">
              {statusResponse === null ? (
                <div className="text-sm text-slate-400">
                  Authoritative session
                  status is currently
                  unavailable. Refresh status
                  before issuing another
                  lifecycle command.
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                  <SnapshotField
                    label="Lifecycle"
                    value={
                      snapshot?.status ??
                      "NO SESSION"
                    }
                  />

                  <SnapshotField
                    label="Active"
                    value={
                      statusResponse.active
                        ? "YES"
                        : "NO"
                    }
                  />

                  <SnapshotField
                    label="Session ID"
                    value={
                      snapshot?.session_id ??
                      "-"
                    }
                  />

                  <SnapshotField
                    label="Strategy"
                    value={
                      snapshot?.strategy_name ??
                      "-"
                    }
                  />

                  <SnapshotField
                    label="Symbol"
                    value={
                      snapshot?.symbol ?? "-"
                    }
                  />

                  <SnapshotField
                    label="Started At"
                    value={
                      snapshot?.started_at ??
                      "-"
                    }
                  />

                  <SnapshotField
                    label="Stopped At"
                    value={
                      snapshot?.stopped_at ??
                      "-"
                    }
                  />
                </div>
              )}
            </CardContent>
          </Card>
        </DashboardSection>

        {snapshot ? (
          <>
            <DashboardSection title="Account State">
              <AccountMetrics
                snapshot={snapshot}
              />
            </DashboardSection>

            <DashboardSection title="Active Position">
              <Card>
                <CardContent className="p-6">
                  {snapshot.active_position ? (
                    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                      <SnapshotField
                        label="Symbol"
                        value={
                          snapshot
                            .active_position
                            .symbol
                        }
                      />

                      <SnapshotField
                        label="Direction"
                        value={
                          snapshot
                            .active_position
                            .direction
                        }
                      />

                      <SnapshotField
                        label="Quantity"
                        value={
                          snapshot
                            .active_position
                            .quantity
                        }
                      />

                      <SnapshotField
                        label="Entry Time"
                        value={
                          snapshot
                            .active_position
                            .entry_time
                        }
                      />

                      <SnapshotField
                        label="Entry Price"
                        value={formatNumber(
                          snapshot
                            .active_position
                            .entry_price,
                        )}
                      />

                      <SnapshotField
                        label="Stop Price"
                        value={formatNumber(
                          snapshot
                            .active_position
                            .stop_price,
                        )}
                      />
                    </div>
                  ) : (
                    <div className="text-sm text-slate-400">
                      No active position.
                    </div>
                  )}
                </CardContent>
              </Card>
            </DashboardSection>

            <DashboardSection title="Latest Execution">
              <Card>
                <CardContent className="p-6">
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                    <SnapshotField
                      label="Event"
                      value={
                        snapshot.last_execution_event ??
                        "-"
                      }
                    />

                    <SnapshotField
                      label="Price"
                      value={formatNumber(
                        snapshot.last_execution_price,
                      )}
                    />

                    <SnapshotField
                      label="Quantity"
                      value={
                        snapshot.last_execution_quantity ??
                        "-"
                      }
                    />
                  </div>
                </CardContent>
              </Card>
            </DashboardSection>

            {snapshot.status ===
              "FAILED" ||
            snapshot.failure_type ||
            snapshot.failure_message ? (
              <DashboardSection title="Runtime Failure">
                <Card>
                  <CardContent className="p-6">
                    <div
                      className="rounded-lg border border-red-900/70 bg-red-950/30 p-4 text-red-300"
                      role="alert"
                    >
                      <div className="font-semibold">
                        {snapshot.failure_type ??
                          "Paper runtime failure"}
                      </div>

                      <div className="mt-2 text-sm">
                        {snapshot.failure_message ??
                          "No failure message was provided."}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </DashboardSection>
            ) : null}
          </>
        ) : null}
      </div>
    </AppLayout>
  );
}
