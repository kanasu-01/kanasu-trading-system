import type { ApiErrorResponse } from "@/types/api";
import { getStagingToken, setStagingToken, stagingFrontend } from "@/stagingSession";

const configuredApiBase =
  import.meta.env.VITE_API_BASE_URL?.trim();

export const API_BASE_URL = configuredApiBase
  ? configuredApiBase.replace(/\/+$/, "")
  : "/api";

export class ApiRequestError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(
    status: number,
    code: string,
    message: string,
  ) {
    super(message);

    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
  }
}

function isApiErrorResponse(
  value: unknown,
): value is ApiErrorResponse {
  if (
    typeof value !== "object" ||
    value === null
  ) {
    return false;
  }

  const candidate = value as Record<
    string,
    unknown
  >;

  return (
    typeof candidate.code === "string" &&
    typeof candidate.message === "string"
  );
}

async function readJson(
  response: Response,
): Promise<unknown> {
  const text = await response.text();

  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit | undefined,
  fallbackMessage: string,
): Promise<T> {
  let response: Response;
  const staging = stagingFrontend();
  const token = staging ? getStagingToken() : null;
  const requestInit = staging
    ? (() => {
        const headers = new Headers(init?.headers);
        if (token) headers.set("Authorization", `Bearer ${token}`);
        else headers.delete("Authorization");
        return {
          ...init,
          headers,
          credentials: "omit" as const,
          cache: "no-store" as const,
        };
      })()
    : init;

  try {
    response = await fetch(
      `${API_BASE_URL}${path}`,
      requestInit,
    );
  } catch {
    throw new ApiRequestError(
      0,
      "network_error",
      "Unable to reach application API",
    );
  }

  if (staging && (response.status === 401 || response.status === 403)) {
    // A delayed response from an older request must not discard a new login.
    if (getStagingToken() === token) setStagingToken(null);
    throw new ApiRequestError(
      401,
      "session_expired",
      "Please sign in again",
    );
  }

  const payload = await readJson(response);

  if (!response.ok) {
    if (isApiErrorResponse(payload)) {
      throw new ApiRequestError(
        response.status,
        payload.code,
        payload.message,
      );
    }

    throw new ApiRequestError(
      response.status,
      "api_request_failed",
      fallbackMessage,
    );
  }

  const contentType =
    response.headers
      .get("content-type")
      ?.toLowerCase() ?? "";

  if (
    !contentType.includes(
      "application/json",
    ) ||
    payload === null
  ) {
    throw new ApiRequestError(
      response.status,
      "invalid_api_response",
      "Application API returned an invalid response",
    );
  }

  return payload as T;
}
