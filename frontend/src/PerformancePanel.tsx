import type { BarRecord } from "../types/BarRecord";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { DashboardSection } from "@/components/dashboard/DashboardSection";

type Props = {
  records: BarRecord[];
  cursor: number;
};

export function PerformancePanel({ records, cursor }: Props) {
  const visible = records.slice(0, cursor + 1);

  let trades = 0;
  let wins = 0;
  let profit = 0;

  let entryPrice: number | null = null;

  for (const r of visible) {
    if (r.signal === "BUY") {
      entryPrice = r.close;
    }

    if (r.signal === "SELL" && entryPrice !== null) {
      trades++;

      const pnl = r.close - entryPrice;
      profit += pnl;

      if (pnl > 0) wins++;

      entryPrice = null;
    }
  }

  const winRate = trades > 0 ? ((wins / trades) * 100).toFixed(1) : "0";

  const avgTrade = trades > 0 ? (profit / trades).toFixed(2) : "0";

  return (
    <DashboardSection title="Performance">
      <div
        className="
        grid
        grid-cols-2
        md:grid-cols-4
        gap-3
      "
      >
        <MetricCard label="Trades" value={trades} />

        <MetricCard label="Win Rate" value={`${winRate}%`} />

        <MetricCard
          label="Total PnL"
          value={profit.toFixed(2)}
          valueClassName={profit >= 0 ? "text-green-400" : "text-red-400"}
        />

        <MetricCard label="Avg Trade" value={avgTrade} />
      </div>
    </DashboardSection>
  );
}
