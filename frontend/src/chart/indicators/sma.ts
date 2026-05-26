// src/chart/indicators/sma.ts

import type { LineData } from "lightweight-charts";
import type { BarRecord } from "../../types/BarRecord";

import { toUnixSeconds } from "../utils/time";

export function buildFastSMAData(
  records: BarRecord[],
  cursor: number
): LineData[] {
  return records
    .slice(0, cursor + 1)
    .map((r) => ({
      time: toUnixSeconds(r.timestamp),
      value: r.decision_snapshot?.fast_sma ?? null,
    }))
    .filter((p) => p.value !== null);
}

export function buildSlowSMAData(
  records: BarRecord[],
  cursor: number
): LineData[] {
  return records
    .slice(0, cursor + 1)
    .map((r) => ({
      time: toUnixSeconds(r.timestamp),
      value: r.decision_snapshot?.slow_sma ?? null,
    }))
    .filter((p) => p.value !== null);
}