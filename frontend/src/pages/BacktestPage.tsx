import { useEffect, useState } from "react";

import { ApiRequestError } from "@/api/apiClient";
import {
  getBacktestConfig,
  runBacktest,
} from "@/api/backtestApi";
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
  BacktestConfigResponse,
  BacktestRunRequest,
  BacktestRunResponse,
  BacktestSummary,
} from "@/types/backtest";

function formatNumber(value: number): string {
  return new Intl.NumberFormat(
    "en-IN",
    {
      maximumFractionDigits: 2,
    },
  ).format(value);
}

function formatPercent(value: number): string {
  return `${formatNumber(value)}%`;
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

function toRfc3339(
  value: string,
  timeZone: string,
): string {
  const match =
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(
      value,
    );

  if (!match) {
    throw new Error(
      "Start and end must use a valid date and time",
    );
  }

  const [
    ,
    year,
    month,
    day,
    hour,
    minute,
  ] = match;

  const utcGuess = new Date(
    Date.UTC(
      Number(year),
      Number(month) - 1,
      Number(day),
      Number(hour),
      Number(minute),
    ),
  );

  const timeZoneName =
    new Intl.DateTimeFormat(
      "en-US",
      {
        timeZone,
        timeZoneName: "longOffset",
        hour: "2-digit",
      },
    )
      .formatToParts(utcGuess)
      .find(
        (part) =>
          part.type === "timeZoneName",
      )?.value;

  if (!timeZoneName) {
    throw new Error(
      `Unable to resolve timezone ${timeZone}`,
    );
  }

  let offset: string;

  if (timeZoneName === "GMT") {
    offset = "+00:00";
  } else if (
    /^GMT[+-]\d{2}:\d{2}$/.test(
      timeZoneName,
    )
  ) {
    offset = timeZoneName.slice(3);
  } else {
    throw new Error(
      `Unsupported timezone offset ${timeZoneName}`,
    );
  }

  return `${value}:00${offset}`;
}

function summaryItems(
  summary: BacktestSummary,
): Array<{
  label: string;
  value: string | number;
}> {
  return [
    {
      label: "Completed Trades",
      value: summary.completed_trade_count,
    },
    {
      label: "Profitable Trades",
      value: summary.net_profitable_trade_count,
    },
    {
      label: "Losing Trades",
      value: summary.net_losing_trade_count,
    },
    {
      label: "Breakeven Trades",
      value: summary.net_breakeven_trade_count,
    },
    {
      label: "Profitable Trade Rate",
      value: formatPercent(
        summary.net_profitable_trade_rate_pct,
      ),
    },
    {
      label: "Mean Positive Return",
      value: formatPercent(
        summary.mean_positive_instrument_return_pct,
      ),
    },
    {
      label: "Mean Negative Return",
      value: formatPercent(
        summary.mean_negative_instrument_return_pct,
      ),
    },
    {
      label: "Mean Instrument Return",
      value: formatPercent(
        summary.mean_instrument_return_pct,
      ),
    },
    {
      label: "Gross Realized PnL",
      value: formatNumber(
        summary.gross_realized_pnl,
      ),
    },
    {
      label: "Net Realized PnL",
      value: formatNumber(
        summary.net_realized_pnl,
      ),
    },
    {
      label: "Mean Net PnL / Trade",
      value: formatNumber(
        summary.mean_net_pnl_per_completed_trade,
      ),
    },
    {
      label: "Transaction Costs",
      value: formatNumber(
        summary.completed_trade_transaction_cost_total,
      ),
    },
    {
      label: "Account PnL",
      value: formatNumber(
        summary.account_pnl,
      ),
    },
    {
      label: "Account Return",
      value: formatPercent(
        summary.account_return_pct,
      ),
    },
    {
      label: "Max Equity Drawdown",
      value: formatPercent(
        summary.max_equity_drawdown_pct,
      ),
    },
  ];
}

const inputClassName =
  "h-8 w-full rounded-lg border border-slate-700 bg-transparent px-2.5 text-sm outline-none focus:border-slate-500";

export function BacktestPage() {
  const [
    config,
    setConfig,
  ] =
    useState<BacktestConfigResponse | null>(
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
    runError,
    setRunError,
  ] =
    useState<string | null>(null);

  const [
    selectedSymbol,
    setSelectedSymbol,
  ] = useState("");

  const [
    selectedTimeframe,
    setSelectedTimeframe,
  ] = useState("");

  const [
    selectedStrategy,
    setSelectedStrategy,
  ] = useState("");

  const [
    selectedTimezone,
    setSelectedTimezone,
  ] = useState("");

  const [startValue, setStartValue] =
    useState("");

  const [endValue, setEndValue] =
    useState("");

  const [
    initialCapital,
    setInitialCapital,
  ] = useState("100000");

  const [
    fastPeriod,
    setFastPeriod,
  ] = useState("20");

  const [
    slowPeriod,
    setSlowPeriod,
  ] = useState("50");

  const [
    backtestResult,
    setBacktestResult,
  ] =
    useState<BacktestRunResponse | null>(
      null,
    );

  const [isRunning, setIsRunning] =
    useState(false);

  useEffect(() => {
    async function loadConfig() {
      try {
        const data =
          await getBacktestConfig();

        setConfig(data);

        setSelectedSymbol(
          data.symbols[0]?.symbol ?? "",
        );

        setSelectedTimeframe(
          data.timeframes[0]?.id ?? "",
        );

        setSelectedStrategy(
          data.strategies[0]?.id ?? "",
        );

        setSelectedTimezone(
          data.timezones[0] ?? "",
        );
      } catch (error) {
        setConfigError(
          errorMessage(
            error,
            "Failed to load backtest configuration",
          ),
        );
      } finally {
        setLoading(false);
      }
    }

    void loadConfig();
  }, []);

  async function handleRunBacktest() {
    setRunError(null);

    const capital =
      Number(initialCapital);

    const fast = Number(fastPeriod);
    const slow = Number(slowPeriod);

    if (
      !selectedSymbol ||
      !selectedTimeframe ||
      !selectedStrategy ||
      !selectedTimezone
    ) {
      setRunError(
        "Select all required configuration values",
      );
      return;
    }

    if (!startValue || !endValue) {
      setRunError(
        "Start and end are required",
      );
      return;
    }

    if (
      !Number.isFinite(capital) ||
      capital <= 0
    ) {
      setRunError(
        "Initial capital must be greater than zero",
      );
      return;
    }

    if (
      !Number.isInteger(fast) ||
      !Number.isInteger(slow) ||
      fast <= 0 ||
      slow <= 0 ||
      fast >= slow
    ) {
      setRunError(
        "SMA periods must be positive integers with fast < slow",
      );
      return;
    }

    try {
      const start = toRfc3339(
        startValue,
        selectedTimezone,
      );

      const end = toRfc3339(
        endValue,
        selectedTimezone,
      );

      if (
        Date.parse(end) <=
        Date.parse(start)
      ) {
        setRunError(
          "End must be after start",
        );
        return;
      }

      const payload: BacktestRunRequest =
        {
          symbol: selectedSymbol,
          timeframe:
            selectedTimeframe,
          strategy_id:
            selectedStrategy,
          start,
          end,
          timezone:
            selectedTimezone,
          initial_capital: capital,
          strategy_params: {
            fast_period: fast,
            slow_period: slow,
          },
        };

      setIsRunning(true);
      setBacktestResult(null);

      const result =
        await runBacktest(payload);

      setBacktestResult(result);
    } catch (error) {
      setRunError(
        errorMessage(
          error,
          "Backtest execution failed",
        ),
      );
    } finally {
      setIsRunning(false);
    }
  }

  if (loading) {
    return (
      <AppLayout>
        <div className="p-6">
          Loading backtest configuration...
        </div>
      </AppLayout>
    );
  }

  if (configError || !config) {
    return (
      <AppLayout>
        <div className="p-6 text-red-400">
          {configError ??
            "Backtest configuration unavailable"}
        </div>
      </AppLayout>
    );
  }

  const canRun =
    Boolean(
      selectedSymbol &&
        selectedTimeframe &&
        selectedStrategy &&
        selectedTimezone &&
        startValue &&
        endValue,
    ) && !isRunning;

  return (
    <AppLayout>
      <div className="p-6">
        <div className="mb-8">
          <div className="mb-2 text-3xl font-bold">
            Backtest Workspace
          </div>

          <div className="text-slate-400">
            Run an authoritative historical
            strategy evaluation
          </div>
        </div>

        <DashboardSection title="Configuration">
          <Card>
            <CardContent className="p-6">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                <div>
                  <div className="mb-2 text-sm text-slate-400">
                    Market
                  </div>

                  <div className="flex h-8 items-center rounded-lg border border-slate-800 px-2.5 text-sm">
                    {config.markets
                      .map(
                        (market) =>
                          market.name,
                      )
                      .join(", ") || "-"}
                  </div>
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
                            {symbol.symbol}
                          </SelectItem>
                        ),
                      )}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <div className="mb-2 text-sm text-slate-400">
                    Timeframe
                  </div>

                  <Select
                    value={
                      selectedTimeframe
                    }
                    onValueChange={
                      setSelectedTimeframe
                    }
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>

                    <SelectContent>
                      {config.timeframes.map(
                        (timeframe) => (
                          <SelectItem
                            key={
                              timeframe.id
                            }
                            value={
                              timeframe.id
                            }
                          >
                            {
                              timeframe.label
                            }
                          </SelectItem>
                        ),
                      )}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <div className="mb-2 text-sm text-slate-400">
                    Strategy
                  </div>

                  <Select
                    value={
                      selectedStrategy
                    }
                    onValueChange={
                      setSelectedStrategy
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
                    Timezone
                  </div>

                  <Select
                    value={
                      selectedTimezone
                    }
                    onValueChange={
                      setSelectedTimezone
                    }
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>

                    <SelectContent>
                      {config.timezones.map(
                        (timezone) => (
                          <SelectItem
                            key={timezone}
                            value={timezone}
                          >
                            {timezone}
                          </SelectItem>
                        ),
                      )}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <label
                    className="mb-2 block text-sm text-slate-400"
                    htmlFor="backtest-start"
                  >
                    Start
                  </label>

                  <input
                    id="backtest-start"
                    aria-label="Backtest start"
                    type="datetime-local"
                    className={
                      inputClassName
                    }
                    value={startValue}
                    onChange={(event) =>
                      setStartValue(
                        event.target.value,
                      )
                    }
                  />
                </div>

                <div>
                  <label
                    className="mb-2 block text-sm text-slate-400"
                    htmlFor="backtest-end"
                  >
                    End
                  </label>

                  <input
                    id="backtest-end"
                    aria-label="Backtest end"
                    type="datetime-local"
                    className={
                      inputClassName
                    }
                    value={endValue}
                    onChange={(event) =>
                      setEndValue(
                        event.target.value,
                      )
                    }
                  />
                </div>

                <div>
                  <label
                    className="mb-2 block text-sm text-slate-400"
                    htmlFor="initial-capital"
                  >
                    Initial Capital
                  </label>

                  <input
                    id="initial-capital"
                    aria-label="Initial capital"
                    type="number"
                    min="0"
                    step="any"
                    className={
                      inputClassName
                    }
                    value={initialCapital}
                    onChange={(event) =>
                      setInitialCapital(
                        event.target.value,
                      )
                    }
                  />
                </div>

                <div>
                  <label
                    className="mb-2 block text-sm text-slate-400"
                    htmlFor="fast-period"
                  >
                    SMA Fast Period
                  </label>

                  <input
                    id="fast-period"
                    aria-label="SMA fast period"
                    type="number"
                    min="1"
                    step="1"
                    className={
                      inputClassName
                    }
                    value={fastPeriod}
                    onChange={(event) =>
                      setFastPeriod(
                        event.target.value,
                      )
                    }
                  />
                </div>

                <div>
                  <label
                    className="mb-2 block text-sm text-slate-400"
                    htmlFor="slow-period"
                  >
                    SMA Slow Period
                  </label>

                  <input
                    id="slow-period"
                    aria-label="SMA slow period"
                    type="number"
                    min="1"
                    step="1"
                    className={
                      inputClassName
                    }
                    value={slowPeriod}
                    onChange={(event) =>
                      setSlowPeriod(
                        event.target.value,
                      )
                    }
                  />
                </div>
              </div>

              {runError ? (
                <div
                  className="mt-5 rounded-lg border border-red-900/70 bg-red-950/30 p-3 text-sm text-red-300"
                  role="alert"
                >
                  {runError}
                </div>
              ) : null}

              <div className="mt-6">
                <Button
                  onClick={
                    handleRunBacktest
                  }
                  disabled={!canRun}
                >
                  {isRunning
                    ? "Running..."
                    : "Run Backtest"}
                </Button>
              </div>
            </CardContent>
          </Card>
        </DashboardSection>

        <DashboardSection title="Results">
          {!backtestResult ? (
            <Card>
              <CardContent className="p-6 text-slate-400">
                {isRunning
                  ? "Running backtest..."
                  : "Run a backtest to view authoritative results."}
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-6">
              <Card>
                <CardContent className="p-6">
                  <div className="grid grid-cols-1 gap-4 text-sm md:grid-cols-2 xl:grid-cols-4">
                    <div>
                      <div className="text-slate-400">
                        Run ID
                      </div>
                      <div className="mt-1 break-all font-medium">
                        {
                          backtestResult.run_id
                        }
                      </div>
                    </div>

                    <div>
                      <div className="text-slate-400">
                        Status
                      </div>
                      <div className="mt-1 font-medium">
                        {
                          backtestResult.status
                        }
                      </div>
                    </div>

                    <div>
                      <div className="text-slate-400">
                        Symbol / Timeframe
                      </div>
                      <div className="mt-1 font-medium">
                        {
                          backtestResult.symbol
                        }{" "}
                        /{" "}
                        {
                          backtestResult.timeframe
                        }
                      </div>
                    </div>

                    <div>
                      <div className="text-slate-400">
                        Strategy
                      </div>
                      <div className="mt-1 font-medium">
                        {
                          backtestResult.strategy_id
                        }
                      </div>
                    </div>

                    <div>
                      <div className="text-slate-400">
                        Start
                      </div>
                      <div className="mt-1 font-medium">
                        {
                          backtestResult.start
                        }
                      </div>
                    </div>

                    <div>
                      <div className="text-slate-400">
                        End
                      </div>
                      <div className="mt-1 font-medium">
                        {
                          backtestResult.end
                        }
                      </div>
                    </div>

                    <div>
                      <div className="text-slate-400">
                        Timezone
                      </div>
                      <div className="mt-1 font-medium">
                        {
                          backtestResult.timezone
                        }
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
                {summaryItems(
                  backtestResult.summary,
                ).map((item) => (
                  <MetricCard
                    key={item.label}
                    label={item.label}
                    value={item.value}
                  />
                ))}
              </div>

              <Card>
                <CardContent className="p-6">
                  <div className="mb-4 text-sm font-semibold text-slate-300">
                    Equity Curve
                  </div>

                  {backtestResult
                    .equity_curve.length ===
                  0 ? (
                    <div className="text-sm text-slate-400">
                      No equity points were
                      returned.
                    </div>
                  ) : (
                    <div className="max-h-80 overflow-auto">
                      <table className="w-full min-w-96 text-left text-sm">
                        <thead className="sticky top-0 bg-slate-950">
                          <tr className="border-b border-slate-800 text-slate-400">
                            <th className="p-2">
                              Timestamp
                            </th>
                            <th className="p-2 text-right">
                              Equity
                            </th>
                          </tr>
                        </thead>

                        <tbody>
                          {backtestResult.equity_curve.map(
                            (point) => (
                              <tr
                                key={
                                  point.timestamp
                                }
                                className="border-b border-slate-900"
                              >
                                <td className="p-2">
                                  {
                                    point.timestamp
                                  }
                                </td>
                                <td className="p-2 text-right">
                                  {formatNumber(
                                    point.equity,
                                  )}
                                </td>
                              </tr>
                            ),
                          )}
                        </tbody>
                      </table>
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardContent className="p-6">
                  <div className="mb-4 text-sm font-semibold text-slate-300">
                    Completed Trades
                  </div>

                  {backtestResult.trades
                    .length === 0 ? (
                    <div className="text-sm text-slate-400">
                      No completed trades were
                      produced for this run.
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full min-w-[1200px] text-left text-sm">
                        <thead>
                          <tr className="border-b border-slate-800 text-slate-400">
                            <th className="p-2">
                              Symbol
                            </th>
                            <th className="p-2">
                              Direction
                            </th>
                            <th className="p-2">
                              Entry
                            </th>
                            <th className="p-2 text-right">
                              Entry Price
                            </th>
                            <th className="p-2">
                              Exit
                            </th>
                            <th className="p-2 text-right">
                              Exit Price
                            </th>
                            <th className="p-2 text-right">
                              Stop
                            </th>
                            <th className="p-2 text-right">
                              Qty
                            </th>
                            <th className="p-2">
                              Exit Reason
                            </th>
                            <th className="p-2 text-right">
                              Gross PnL
                            </th>
                            <th className="p-2 text-right">
                              Costs
                            </th>
                            <th className="p-2 text-right">
                              Net PnL
                            </th>
                            <th className="p-2 text-right">
                              Return
                            </th>
                          </tr>
                        </thead>

                        <tbody>
                          {backtestResult.trades.map(
                            (
                              trade,
                              index,
                            ) => (
                              <tr
                                key={`${trade.entry_time}-${trade.exit_time}-${index}`}
                                className="border-b border-slate-900"
                              >
                                <td className="p-2">
                                  {
                                    trade.symbol
                                  }
                                </td>
                                <td className="p-2">
                                  {
                                    trade.direction
                                  }
                                </td>
                                <td className="p-2">
                                  {
                                    trade.entry_time
                                  }
                                </td>
                                <td className="p-2 text-right">
                                  {formatNumber(
                                    trade.entry_price,
                                  )}
                                </td>
                                <td className="p-2">
                                  {
                                    trade.exit_time
                                  }
                                </td>
                                <td className="p-2 text-right">
                                  {formatNumber(
                                    trade.exit_price,
                                  )}
                                </td>
                                <td className="p-2 text-right">
                                  {formatNumber(
                                    trade.stop_price,
                                  )}
                                </td>
                                <td className="p-2 text-right">
                                  {
                                    trade.quantity
                                  }
                                </td>
                                <td className="p-2">
                                  {
                                    trade.exit_reason
                                  }
                                </td>
                                <td className="p-2 text-right">
                                  {formatNumber(
                                    trade.gross_pnl,
                                  )}
                                </td>
                                <td className="p-2 text-right">
                                  {formatNumber(
                                    trade.transaction_cost,
                                  )}
                                </td>
                                <td className="p-2 text-right">
                                  {formatNumber(
                                    trade.net_pnl,
                                  )}
                                </td>
                                <td className="p-2 text-right">
                                  {formatPercent(
                                    trade.instrument_return_pct,
                                  )}
                                </td>
                              </tr>
                            ),
                          )}
                        </tbody>
                      </table>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </DashboardSection>
      </div>
    </AppLayout>
  );
}
