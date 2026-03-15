import type { BarRecord } from "../types/BarRecord";

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

  const winRate =
    trades > 0 ? ((wins / trades) * 100).toFixed(1) : "0";

  const avgTrade =
    trades > 0 ? (profit / trades).toFixed(2) : "0";

  return (
    <div
      style={{
        borderTop: "1px solid #333",
        paddingTop: 6,
        display: "flex",
        gap: 20,
        fontSize: 13,
      }}
    >
      <div>Trades: {trades}</div>
      <div>Win Rate: {winRate}%</div>
      <div>Total PnL: {profit.toFixed(2)}</div>
      <div>Avg Trade: {avgTrade}</div>
    </div>
  );
}