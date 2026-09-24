import { apiRequest } from "@/api/apiClient";

import type {
  BacktestConfigResponse,
  BacktestRunRequest,
  BacktestRunResponse,
} from "@/types/backtest";

export async function getBacktestConfig():
Promise<BacktestConfigResponse> {
  return apiRequest<BacktestConfigResponse>(
    "/backtest/config",
    undefined,
    "Failed to fetch backtest config",
  );
}

export async function runBacktest(
  payload: BacktestRunRequest,
): Promise<BacktestRunResponse> {
  return apiRequest<BacktestRunResponse>(
    "/backtest/run",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    },
    "Backtest execution failed",
  );
}
