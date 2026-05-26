// src/chart/overlays/tradeZones.ts

import {
  AreaSeries,
} from "lightweight-charts";

import type {
  IChartApi,
  ISeriesApi,
} from "lightweight-charts";

import type { BarRecord } from "../../types/BarRecord";

import { toUnixSeconds } from "../utils/time";

export function renderTradeZones(
  chart: IChartApi,
  records: BarRecord[],
  cursor: number,
  tradeAreasRef: React.MutableRefObject<
    ISeriesApi<"Area">[]
  >
) {
  // remove old areas
  tradeAreasRef.current.forEach((series) => {
    chart.removeSeries(series);
  });

  tradeAreasRef.current = [];

  let entry: BarRecord | null = null;

  let tradeData: {
    time: ReturnType<typeof toUnixSeconds>;
    value: number;
  }[] = [];

  for (const r of records.slice(0, cursor + 1)) {
    const t = toUnixSeconds(r.timestamp);

    if (r.signal === "BUY") {
      entry = r;
      tradeData = [];
    }

    if (entry) {
      tradeData.push({
        time: t,
        value: r.close,
      });
    }

    if (r.signal === "SELL" && entry) {
      const entryPrice = entry.close;
      const exitPrice = r.close;

      const isWinningTrade =
        exitPrice > entryPrice;

      const areaColor = isWinningTrade
        ? "rgba(34,197,94,0.18)"
        : "rgba(239,68,68,0.18)";

      const area = chart.addSeries(
        AreaSeries,
        {
          topColor: areaColor,
          bottomColor: areaColor,
          lineColor: "rgba(0,0,0,0)",
        }
      );

      area.setData(tradeData);

      tradeAreasRef.current.push(area);

      entry = null;
    }
  }
}