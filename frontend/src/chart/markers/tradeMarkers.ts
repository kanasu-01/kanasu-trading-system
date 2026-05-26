// src/chart/markers/tradeMarkers.ts

import type {
  SeriesMarker,
  Time,
} from "lightweight-charts";

import type { BarRecord } from "../../types/BarRecord";

import { toUnixSeconds } from "../utils/time";

export function buildTradeMarkers(
  records: BarRecord[],
  cursor: number
): SeriesMarker<Time>[] {
  return records
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
    .filter(
      (
        marker
      ): marker is SeriesMarker<Time> =>
        marker !== null
    );
}