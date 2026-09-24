import type {
  SeriesMarker,
  Time,
} from "lightweight-charts";

import type { BarRecord } from "../../types/BarRecord";

import { toUnixSeconds } from "../utils/time";

export function buildTradeMarkers(
  records: BarRecord[],
  cursor: number,
): SeriesMarker<Time>[] {
  const markers: SeriesMarker<Time>[] = [];

  for (
    const record of records.slice(
      0,
      cursor + 1,
    )
  ) {
    if (record.signal === "BUY") {
      markers.push({
        time: toUnixSeconds(
          record.timestamp,
        ),
        position: "belowBar",
        color: "#22c55e",
        shape: "arrowUp",
        text: "BUY",
      });
    }

    if (record.signal === "SELL") {
      markers.push({
        time: toUnixSeconds(
          record.timestamp,
        ),
        position: "aboveBar",
        color: "#ef4444",
        shape: "arrowDown",
        text: "SELL",
      });
    }
  }

  return markers;
}
