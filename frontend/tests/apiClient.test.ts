import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import {
  apiRequest,
} from "@/api/apiClient";

describe("apiRequest", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal(
      "fetch",
      fetchMock,
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("preserves structured API errors", async () => {
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({
          code: "example_conflict",
          message: "Example conflict",
        }),
        {
          status: 409,
          headers: {
            "Content-Type":
              "application/json",
          },
        },
      ),
    );

    await expect(
      apiRequest(
        "/example",
        undefined,
        "Fallback",
      ),
    ).rejects.toMatchObject({
      status: 409,
      code: "example_conflict",
      message: "Example conflict",
    });
  });

  it("rejects successful non-JSON responses", async () => {
    fetchMock.mockResolvedValue(
      new Response(
        "<!doctype html>",
        {
          status: 200,
          headers: {
            "Content-Type":
              "text/html",
          },
        },
      ),
    );

    await expect(
      apiRequest(
        "/example",
        undefined,
        "Fallback",
      ),
    ).rejects.toMatchObject({
      status: 200,
      code: "invalid_api_response",
    });
  });
});
