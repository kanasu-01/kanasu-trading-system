import { AppLayout } from "@/app/AppLayout";
import { Card, CardContent } from "@/components/ui/card";

import { Button } from "@/components/ui/button";

import { DashboardSection } from "@/components/dashboard/DashboardSection";

import { useEffect, useState } from "react";

import { getBacktestConfig, runBacktest } from "@/api/backtestApi";

import type { BacktestConfigResponse } from "@/types/backtest";

import { useNavigate } from "react-router-dom";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export function BacktestPage() {
  const [config, setConfig] = useState<BacktestConfigResponse | null>(null);

  const [loading, setLoading] = useState(true);

  const [error, setError] = useState<string | null>(null);

  const [selectedMarket, setSelectedMarket] = useState("");

  const [selectedSymbol, setSelectedSymbol] = useState("");

  const [selectedTimeframe, setSelectedTimeframe] = useState("");

  const [selectedStrategy, setSelectedStrategy] = useState("");

  const [backtestResult, setBacktestResult] = useState<any>(null);

  const [isRunning, setIsRunning] = useState(false);

  const navigate = useNavigate();

  useEffect(() => {
    async function loadConfig() {
      try {
        const data = await getBacktestConfig();

        setConfig(data);

        if (data.markets.length > 0) {
          setSelectedMarket(data.markets[0].id);
        }

        if (data.symbols.length > 0) {
          setSelectedSymbol(data.symbols[0].symbol);
        }

        if (data.timeframes.length > 0) {
          setSelectedTimeframe(data.timeframes[0].id);
        }

        if (data.strategies.length > 0) {
          setSelectedStrategy(data.strategies[0].id);
        }
      } catch (err) {
        setError("Failed to load config");
      } finally {
        setLoading(false);
      }
    }

    loadConfig();
  }, []);

  if (loading) {
    return (
      <AppLayout>
        <div className="p-6">Loading backtest config...</div>
      </AppLayout>
    );
  }

  async function handleRunBacktest() {
    try {
      setIsRunning(true);

      const result = await runBacktest({
        market: selectedMarket,

        symbol: selectedSymbol,

        timeframe: selectedTimeframe,

        strategy_id: selectedStrategy,

        from_date: "2025-01-01",

        to_date: "2025-03-01",

        initial_capital: 100000,
      });

      setBacktestResult(result);
    } catch (err) {
      console.error(err);

      alert("Failed to run backtest");
    } finally {
      setIsRunning(false);
    }
  }

  if (error || !config) {
    return (
      <AppLayout>
        <div className="p-6 text-red-400">{error ?? "Config unavailable"}</div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="p-6">
        {/* PAGE TITLE */}
        <div className="mb-8">
          <div
            className="
            text-3xl
            font-bold
            mb-2
          "
          >
            Backtest Workspace
          </div>

          <div
            className="
            text-slate-400
          "
          >
            Configure and run strategy backtests
          </div>
        </div>

        {/* CONFIGURATION */}
        <DashboardSection title="Configuration">
          <Card>
            <CardContent className="p-6">
              <div
                className="
                grid
                grid-cols-1
                md:grid-cols-2
                xl:grid-cols-4
                gap-4
              "
              >
                {/* Market */}
                <div>
                  <div
                    className="
                      text-sm
                      mb-2
                    text-slate-400
                    "
                  >
                    Market
                  </div>

                  <Select
                    value={selectedMarket}
                    onValueChange={setSelectedMarket}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>

                    <SelectContent>
                      {config.markets.map((market) => (
                        <SelectItem key={market.id} value={market.id}>
                          {market.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Symbol */}
                <div>
                  <div
                    className="
                      text-sm
                      mb-2
                    text-slate-400
                    "
                  >
                    Symbol
                  </div>

                  <Select
                    value={selectedSymbol}
                    onValueChange={setSelectedSymbol}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>

                    <SelectContent>
                      {config.symbols.map((symbol) => (
                        <SelectItem key={symbol.symbol} value={symbol.symbol}>
                          {symbol.symbol}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Timeframe */}
                <div>
                  <div className="text-sm mb-2 text-slate-400">Timeframe</div>

                  <Select
                    value={selectedTimeframe}
                    onValueChange={setSelectedTimeframe}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>

                    <SelectContent>
                      {config.timeframes.map((timeframe) => (
                        <SelectItem key={timeframe.id} value={timeframe.id}>
                          {timeframe.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Strategy */}
                <div>
                  <div className="text-sm mb-2 text-slate-400">Strategy</div>

                  <Select
                    value={selectedStrategy}
                    onValueChange={setSelectedStrategy}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>

                    <SelectContent>
                      {config.strategies.map((strategy) => (
                        <SelectItem key={strategy.id} value={strategy.id}>
                          {strategy.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* ACTIONS */}
              <div className="mt-6 flex gap-3">
                <Button onClick={handleRunBacktest} disabled={isRunning}>
                  {isRunning ? "Running..." : "Run Backtest"}
                </Button>

                <Button
                  variant="outline"
                  onClick={() => navigate("/replay")}
                  disabled={!backtestResult?.replay_available}
                >
                  Open Replay
                </Button>
              </div>
            </CardContent>
          </Card>
        </DashboardSection>

        {/* RESULTS */}
        <DashboardSection title="Results">
          <Card>
            <CardContent className="p-6">
              {!backtestResult ? (
                <div className="text-slate-400">
                  Backtest results will appear here.
                </div>
              ) : (
                <div
                  className="
      grid
      grid-cols-1
      md:grid-cols-2
      xl:grid-cols-5
      gap-4
    "
                >
                  <div
                    className="
        border
        border-slate-800
        rounded-lg
        p-4
      "
                  >
                    <div className="text-sm text-slate-400">Trades</div>

                    <div className="text-2xl font-bold mt-2">
                      {backtestResult.summary.total_trades}
                    </div>
                  </div>

                  <div
                    className="
        border
        border-slate-800
        rounded-lg
        p-4
      "
                  >
                    <div className="text-sm text-slate-400">Win Rate</div>

                    <div className="text-2xl font-bold mt-2">
                      {backtestResult.summary.win_rate}%
                    </div>
                  </div>

                  <div
                    className="
        border
        border-slate-800
        rounded-lg
        p-4
      "
                  >
                    <div className="text-sm text-slate-400">Net PnL</div>

                    <div className="text-2xl font-bold mt-2">
                      {backtestResult.summary.net_pnl}
                    </div>
                  </div>

                  <div
                    className="
        border
        border-slate-800
        rounded-lg
        p-4
      "
                  >
                    <div className="text-sm text-slate-400">Max Drawdown</div>

                    <div className="text-2xl font-bold mt-2">
                      {backtestResult.summary.max_drawdown}%
                    </div>
                  </div>

                  <div
                    className="
        border
        border-slate-800
        rounded-lg
        p-4
      "
                  >
                    <div className="text-sm text-slate-400">Expectancy</div>

                    <div className="text-2xl font-bold mt-2">
                      {backtestResult.summary.expectancy}
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </DashboardSection>
      </div>
    </AppLayout>
  );
}
