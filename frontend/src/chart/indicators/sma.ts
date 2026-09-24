import type {
  LineData,
} from "lightweight-charts";

import type {
  BarRecord,
} from "../../types/BarRecord";

import {
  toUnixSeconds,
} from "../utils/time";

export function buildFastSMAData(
  records: BarRecord[],
  cursor: number,
): LineData[] {
  const points: LineData[] = [];

  for (
    const record of records.slice(
      0,
      cursor + 1,
    )
  ) {
    const value =
      record.decision_snapshot.fast_sma;

    if (typeof value !== "number") {
      continue;
    }

    points.push({
      time: toUnixSeconds(
        record.timestamp,
      ),
      value,
    });
  }

  return points;
}

export function buildSlowSMAData(
  records: BarRecord[],
  cursor: number,
): LineData[] {
  const points: LineData[] = [];

  for (
    const record of records.slice(
      0,
      cursor + 1,
    )
  ) {
    const value =
      record.decision_snapshot.slow_sma;

    if (typeof value !== "number") {
      continue;
    }

    points.push({
      time: toUnixSeconds(
        record.timestamp,
      ),
      value,
    });
  }

  return points;
}
