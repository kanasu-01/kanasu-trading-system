import type {
  PaperTradingConfigResponse,
  PaperTradingStartRequest,
  PaperTradingStartResponse,
  PaperTradingStopResponse,
  PaperTradingStatusResponse,
} from "@/types/paperTrading";

const API_BASE_URL =
  "http://100.118.17.51:8000/api";

//
// GET CONFIG
//

export async function getPaperTradingConfig():
Promise<PaperTradingConfigResponse> {
  const response = await fetch(
    `${API_BASE_URL}/paper-trading/config`
  );

  if (!response.ok) {
    throw new Error(
      "Failed to fetch paper trading config"
    );
  }

  return response.json();
}

//
// START
//

export async function startPaperTrading(
  payload: PaperTradingStartRequest
): Promise<PaperTradingStartResponse> {
  const response = await fetch(
    `${API_BASE_URL}/paper-trading/start`,
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
      "Failed to start paper trading"
    );
  }

  return response.json();
}

//
// STOP
//

export async function stopPaperTrading():
Promise<PaperTradingStopResponse> {
  const response = await fetch(
    `${API_BASE_URL}/paper-trading/stop`,
    {
      method: "POST",
    }
  );

  if (!response.ok) {
    throw new Error(
      "Failed to stop paper trading"
    );
  }

  return response.json();
}

//
// STATUS
//

export async function getPaperTradingStatus():
Promise<PaperTradingStatusResponse> {
  const response = await fetch(
    `${API_BASE_URL}/paper-trading/status`
  );

  if (!response.ok) {
    throw new Error(
      "Failed to fetch paper trading status"
    );
  }

  return response.json();
}