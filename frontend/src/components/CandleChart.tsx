import { useEffect, useRef } from "react";
import {
  createChart,
  CandlestickSeries,
  createSeriesMarkers,
  LineSeries,
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
  const

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

    chartRef.current = chart;
    seriesRef.current = candleSeries;

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
            color:"#ef4444",
            shape: "arrowDown" as const,
            text: "SELL"
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
      style={{ width: "100%", height:"100%", borderRadius: 8 }}
    />
  );
}
