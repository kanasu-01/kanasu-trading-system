import type {
  BacktestConfigResponse,
  BacktestRunRequest,
  BacktestRunResponse,
} from "@/types/backtest";

const API_BASE_URL =
  "http://100.118.17.51:8000/api";

//
// GET BACKTEST CONFIG
//

export async function getBacktestConfig():
Promise<BacktestConfigResponse> {
  const response = await fetch(
    `${API_BASE_URL}/backtest/config`
  );

  if (!response.ok) {
    throw new Error(
      "Failed to fetch backtest config"
    );
  }

  return response.json();
}

//
// RUN BACKTEST
//

export async function runBacktest(
  payload: BacktestRunRequest
): Promise<BacktestRunResponse> {
  const response = await fetch(
    `${API_BASE_URL}/backtest/run`,
    {
      method: "POST",

      headers: {
        "Content-Type":
          "application/json",
      },

      body: JSON.stringify(payload),
    }
  );

  if (!response.ok) {
    throw new Error(
      "Failed to run backtest"
    );
  }

  return response.json();
}