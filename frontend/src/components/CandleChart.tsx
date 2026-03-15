import { useEffect, useRef } from "react";
import {
  createChart,
  CandlestickSeries,
  createSeriesMarkers,
  LineSeries,
  AreaSeries,
} from "lightweight-charts";

import type {
  IChartApi,
  ISeriesApi,
  CandlestickData,
} from "lightweight-charts";
import type { BarRecord } from "../types/BarRecord";

function toUnixSeconds(iso: string): number {
  return Math.floor(new Date(iso).getTime() / 1000);
}

type Props = {
  records: BarRecord[];
  cursor: number;
};

export function CandleChart({ records, cursor }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const fastSMARef = useRef<ISeriesApi<"Line"> | null>(null);
  const slowSMARef = useRef<ISeriesApi<"Line"> | null>(null);
  const tradeAreasRef = useRef<ISeriesApi<"Area">[]>([]);

  // -----------------------------------------
  // Create chart ONCE
  // -----------------------------------------
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
      layout: {
        background: { color: "#0f172a" },
        textColor: "#cbd5f5",
      },
      grid: {
        vertLines: { color: "#1e293b" },
        horzLines: { color: "#1e293b" },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
      },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    const fastSMA = chart.addSeries(LineSeries, {
      color: "#5dfa15",
      lineWidth: 2,
    });

    const slowSMA = chart.addSeries(LineSeries, {
      color: "#7a4ae0",
      lineWidth: 2,
    });

    chartRef.current = chart;
    seriesRef.current = candleSeries;
    fastSMARef.current = fastSMA;
    slowSMARef.current = slowSMA;

    return () => {
      chart.remove();
    };
  }, []);

  // -----------------------------------------
  // Update candles as replay advances
  // -----------------------------------------
  useEffect(() => {
    if (!seriesRef.current) return;

    const visibleBars: CandlestickData[] = records
      .slice(0, cursor + 1)
      .map((r) => ({
        time: toUnixSeconds(r.timestamp),
        open: r.open,
        high: r.high,
        low: r.low,
        close: r.close,
      }));

    seriesRef.current.setData(visibleBars);

    //------------------------------------------
    // Update SMAs as replay advances
    //------------------------------------------

    if (fastSMARef.current && slowSMARef.current) {
      const fastSMAData = records
        .slice(0, cursor + 1)
        .map((r) => ({
          time: toUnixSeconds(r.timestamp),
          value: r.decision_snapshot?.fast_sma ?? null,
        }))
        .filter((p) => p.value !== null);

      const slowSMAData = records
        .slice(0, cursor + 1)
        .map((r) => ({
          time: toUnixSeconds(r.timestamp),
          value: r.decision_snapshot?.slow_sma ?? null,
        }))
        .filter((p) => p.value !== null);

      fastSMARef.current.setData(fastSMAData);
      slowSMARef.current.setData(slowSMAData);
    }

    //------------------------------------------
    // Highlight trade zones
    //------------------------------------------

    if (chartRef.current) {
      // remove old trade areas
      tradeAreasRef.current.forEach((series) => {
        chartRef.current?.removeSeries(series);
      });

      tradeAreasRef.current = [];

      let entry: BarRecord | null = null;
      let tradeData: { time: number; value: number }[] = [];

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

          const isWinningTrade = exitPrice > entryPrice;

          const areaColor = isWinningTrade
            ? "rgba(34,197,94,0.18)" // green
            : "rgba(239,68,68,0.18)"; // red

          const area = chartRef.current.addSeries(AreaSeries, {
            topColor: areaColor,
            bottomColor: areaColor,
            lineColor: "rgba(0,0,0,0)",
          });

          area.setData(tradeData);

          tradeAreasRef.current.push(area);

          entry = null;
        }
      }
    }

    const markers = records
      .slice(0, cursor + 1)
      .map((r) => {
        if (r.signal === "BUY") {
          return {
            time: toUnixSeconds(r.timestamp),
            position: "belowBar" as const,
            color: "#22c55e",
            shape: "arrowUp" as const,
            text: "BUY",
          };
        }
        if (r.signal === "SELL") {
          return {
            time: toUnixSeconds(r.timestamp),
            position: "aboveBar" as const,
            color: "#ef4444",
            shape: "arrowDown" as const,
            text: "SELL",
          };
        }
        return null;
      })
      .filter(Boolean);

    createSeriesMarkers(seriesRef.current, markers);
  }, [records, cursor]);

  return (
    <div
      ref={containerRef}
      style={{ width: "100%", height: "100%", borderRadius: 8 }}
    />
  );
}
