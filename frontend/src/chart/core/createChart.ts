// src/chart/core/createChart.ts

import {
  createChart,
  CandlestickSeries,
  LineSeries,
} from "lightweight-charts";

import type {
  IChartApi,
  ISeriesApi,
} from "lightweight-charts";

type ChartResult = {
  chart: IChartApi;
  candleSeries: ISeriesApi<"Candlestick">;
  fastSMA: ISeriesApi<"Line">;
  slowSMA: ISeriesApi<"Line">;
};

export function createKanasuChart(
  container: HTMLDivElement
): ChartResult {
  const chart = createChart(container, {
    width: container.clientWidth,
    height: container.clientHeight,

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

  return {
    chart,
    candleSeries,
    fastSMA,
    slowSMA,
  };
}