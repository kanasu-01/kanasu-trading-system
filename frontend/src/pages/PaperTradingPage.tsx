// frontend/src/pages/PaperTradingPage.tsx

import { useEffect, useState } from "react";

import { AppLayout } from "@/app/AppLayout";

import { DashboardSection } from "@/components/dashboard/DashboardSection";

import { Card, CardContent } from "@/components/ui/card";

import { Button } from "@/components/ui/button";

import {
  getPaperTradingConfig,
  startPaperTrading,
  stopPaperTrading,
  getPaperTradingStatus,
} from "@/api/paperTradingApi";

import type {
  PaperTradingConfigResponse,
  PaperTradingStatusResponse,
} from "@/types/paperTrading";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export function PaperTradingPage() {
  const [config, setConfig] = useState<PaperTradingConfigResponse | null>(null);

  const [loading, setLoading] = useState(true);

  const [selectedStrategy, setSelectedStrategy] = useState("");

  const [selectedSymbol, setSelectedSymbol] = useState("");

  const [isStarting, setIsStarting] = useState(false);

  const [isStopping, setIsStopping] = useState(false);

  const [sessionStatus, setSessionStatus] = useState("STOPPED");

  const [sessionId, setSessionId] = useState<string | null>(null);

  const [statusResponse, setStatusResponse] =
    useState<PaperTradingStatusResponse | null>(null);

  useEffect(() => {
    async function loadConfig() {
      try {
        const data = await getPaperTradingConfig();

        setConfig(data);

        const status = await getPaperTradingStatus();

        setStatusResponse(status);

        if (data.strategies.length > 0) {
          setSelectedStrategy(data.strategies[0].id);
        }

        if (data.symbols.length > 0) {
          setSelectedSymbol(data.symbols[0].symbol);
        }
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }

    loadConfig();
  }, []);

  async function handleStartPaperTrading() {
    try {
      setIsStarting(true);

      const result = await startPaperTrading({
        symbol: selectedSymbol,
        strategy_id: selectedStrategy,
      });

      setSessionStatus(result.status.toUpperCase());

      setSessionId(result.session_id);

      console.log("Paper trading started:", result);

      alert(`Paper Trading Started\n\nSession: ${result.session_id}`);
    } catch (err) {
      console.error(err);

      alert("Failed to start paper trading");
    } finally {
      setIsStarting(false);
    }
  }

  async function handleStopPaperTrading() {
    try {
      setIsStopping(true);

      const result = await stopPaperTrading();

      setSessionStatus(result.status.toUpperCase());

      setSessionId(null);

      console.log("Paper trading stopped:", result);

      alert("Paper Trading Stopped");
    } catch (err) {
      console.error(err);

      alert("Failed to stop paper trading");
    } finally {
      setIsStopping(false);
    }
  }

  async function loadStatus() {
    try {
      const data = await getPaperTradingStatus();

      setStatusResponse(data);
    } catch (err) {
      console.error(err);
    }
  }

  if (loading) {
    return (
      <AppLayout>
        <div className="p-6">Loading paper trading config...</div>
      </AppLayout>
    );
  }

  if (!config) {
    return (
      <AppLayout>
        <div className="p-6 text-red-400">Config unavailable</div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="p-6">
        {/* PAGE TITLE */}
        <div className="mb-8">
          <div className="text-3xl font-bold mb-2">Paper Trading Runtime</div>

          <div className="text-slate-400">
            Monitor and control paper trading sessions
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
                  gap-4
                "
              >
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

                {/* Symbol */}
                <div>
                  <div className="text-sm mb-2 text-slate-400">Symbol</div>

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
              </div>

              {/* ACTIONS */}
              <div className="mt-6 flex gap-3">
                <Button onClick={handleStartPaperTrading} disabled={isStarting}>
                  {isStarting ? "Starting..." : "Start Paper Trading"}
                </Button>

                <Button
                  variant="outline"
                  onClick={handleStopPaperTrading}
                  disabled={isStopping}
                >
                  {isStopping ? "Stopping..." : "Stop Session"}
                </Button>
              </div>
            </CardContent>
          </Card>
        </DashboardSection>
        <DashboardSection title="Session Status">
          <Card>
            <CardContent className="p-6">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-sm text-slate-400">Status</div>

                  <div className="font-medium">{sessionStatus}</div>
                </div>

                <div>
                  <div className="text-sm text-slate-400">Session Id</div>

                  <div className="font-medium">{sessionId ?? "-"}</div>
                </div>

                <div>
                  <div className="text-sm text-slate-400">Strategy</div>

                  <div className="font-medium">{selectedStrategy || "-"}</div>
                </div>

                <div>
                  <div className="text-sm text-slate-400">Symbol</div>

                  <div className="font-medium">{selectedSymbol || "-"}</div>
                </div>
              </div>
            </CardContent>
          </Card>
        </DashboardSection>

        {/*         <DashboardSection title="Active Position">
          <Card>
            <CardContent className="p-6">
              {statusResponse?.active_position ? (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-sm text-slate-400">Side</div>

                    <div className="font-medium">
                      {statusResponse.active_position.side}
                    </div>
                  </div>

                  <div>
                    <div className="text-sm text-slate-400">Quantity</div>

                    <div className="font-medium">
                      {statusResponse.active_position.quantity}
                    </div>
                  </div>

                  <div>
                    <div className="text-sm text-slate-400">Entry Price</div>

                    <div className="font-medium">
                      {statusResponse.active_position.entry_price}
                    </div>
                  </div>

                  <div>
                    <div className="text-sm text-slate-400">Current Price</div>

                    <div className="font-medium">
                      {statusResponse.active_position.current_price}
                    </div>
                  </div>

                  <div>
                    <div className="text-sm text-slate-400">Unrealized PnL</div>

                    <div className="font-medium">
                      {statusResponse.active_position.unrealized_pnl}
                    </div>
                  </div>
                </div>
              ) : (
                <div>No active position</div>
              )}
            </CardContent>
          </Card>
        </DashboardSection> */}
        {/*         <DashboardSection title="Trade Log">
          <Card>
            <CardContent className="p-6">
              <div className="space-y-3">
                {(statusResponse?.trades ?? []).map((trade, index) => (
                  <div
                    key={index}
                    className="
                border
                border-slate-700
                rounded-md
                p-3
              "
                  >
                    <div className="grid grid-cols-5 gap-4">
                      <div>
                        <div className="text-xs text-slate-400">Time</div>

                        <div>{trade.time}</div>
                      </div>

                      <div>
                        <div className="text-xs text-slate-400">Symbol</div>

                        <div>{trade.symbol}</div>
                      </div>

                      <div>
                        <div className="text-xs text-slate-400">Side</div>

                        <div>{trade.side}</div>
                      </div>

                      <div>
                        <div className="text-xs text-slate-400">Price</div>

                        <div>{trade.price}</div>
                      </div>

                      <div>
                        <div className="text-xs text-slate-400">Qty</div>

                        <div>{trade.quantity}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </DashboardSection> */}
      </div>
    </AppLayout>
  );
}
