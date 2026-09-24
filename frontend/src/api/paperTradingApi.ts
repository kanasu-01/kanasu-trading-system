import { apiRequest } from "@/api/apiClient";

import type {
  PaperTradingConfigResponse,
  PaperTradingStartRequest,
  PaperTradingStartResponse,
  PaperTradingStatusResponse,
  PaperTradingStopResponse,
} from "@/types/paperTrading";

export async function getPaperTradingConfig():
Promise<PaperTradingConfigResponse> {
  return apiRequest<PaperTradingConfigResponse>(
    "/paper-trading/config",
    undefined,
    "Failed to fetch paper trading config",
  );
}

export async function startPaperTrading(
  payload: PaperTradingStartRequest,
): Promise<PaperTradingStartResponse> {
  return apiRequest<PaperTradingStartResponse>(
    "/paper-trading/start",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    },
    "Paper trading start failed",
  );
}

export async function stopPaperTrading():
Promise<PaperTradingStopResponse> {
  return apiRequest<PaperTradingStopResponse>(
    "/paper-trading/stop",
    {
      method: "POST",
    },
    "Paper trading stop failed",
  );
}

export async function getPaperTradingStatus():
Promise<PaperTradingStatusResponse> {
  return apiRequest<PaperTradingStatusResponse>(
    "/paper-trading/status",
    undefined,
    "Failed to fetch paper trading status",
  );
}
