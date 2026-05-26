import { useEffect, useRef } from "react";
import { toUnixSeconds } from "../chart/utils/time";
import { createKanasuChart } from "../chart/core/createChart";
import { buildFastSMAData, buildSlowSMAData } from "../chart/indicators/sma";
import { buildTradeMarkers } from "../chart/markers/tradeMarkers";
import { createSeriesMarkers, AreaSeries } from "lightweight-charts";
import { renderTradeZones } from "../chart/overlays/tradeZones";

import type {
  IChartApi,
  ISeriesApi,
  CandlestickData,
} from "lightweight-charts";
import type { BarRecord } from "../types/BarRecord";
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

    const { chart, candleSeries, fastSMA, slowSMA } = createKanasuChart(
      containerRef.current,
    );

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
      const fastSMAData = buildFastSMAData(records, cursor);

      const slowSMAData = buildSlowSMAData(records, cursor);

      fastSMARef.current.setData(fastSMAData);
      slowSMARef.current.setData(slowSMAData);
    }

    //------------------------------------------
    // Highlight trade zones
    //------------------------------------------

    if (chartRef.current) {
      renderTradeZones(chartRef.current, records, cursor, tradeAreasRef);
    }

    const markers = buildTradeMarkers(records, cursor);

    createSeriesMarkers(seriesRef.current, markers);
  }, [records, cursor]);

  return (
    <div
      ref={containerRef}
      style={{ width: "100%", height: "100%", borderRadius: 8 }}
    />
  );
}
