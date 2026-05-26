// src/chart/utils/time.ts

import type { UTCTimestamp } from "lightweight-charts";

export function toUnixSeconds(iso: string): UTCTimestamp {
  return Math.floor(
    new Date(iso).getTime() / 1000
  ) as UTCTimestamp;
}