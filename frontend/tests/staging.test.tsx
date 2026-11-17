import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../src/App";
import { apiRequest } from "../src/api/apiClient";
import { LoginGate, SessionControls } from "../src/staging";
import { AppLayout } from "../src/app/AppLayout";
import { getStagingToken, setStagingToken, stagingFrontend } from "../src/stagingSession";

vi.mock("../src/pages/HomePage", () => ({ HomePage: () => <p>Home fixture</p> }));
vi.mock("../src/pages/BacktestPage", () => ({ BacktestPage: () => <p>Backtest fixture</p> }));
vi.mock("../src/pages/PaperTradingPage", () => ({ PaperTradingPage: () => <p>Paper fixture</p> }));
vi.mock("../src/pages/ReplayPage", () => ({ ReplayPage: () => <p>Replay fixture</p> }));
vi.mock("../src/pages/PortfolioPage", () => ({ PortfolioPage: () => <p>Portfolio fixture</p> }));

beforeEach(() => { setStagingToken(null); window.localStorage.clear(); });
afterEach(() => { setStagingToken(null); vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

describe("staging UI boundary", () => {
  it("preserves ordinary local UI but gates staging", () => {
    vi.stubEnv("VITE_KANASU_STAGING_AUTH", "false");
    expect(stagingFrontend()).toBe(false);
    const view = render(<MemoryRouter><App /></MemoryRouter>);
    expect(screen.getByText("Home fixture")).toBeInTheDocument();
    view.unmount();
    vi.stubEnv("VITE_KANASU_STAGING_AUTH", "true");
    render(<MemoryRouter><App /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "Kanasu staging login" })).toBeInTheDocument();
  });

  it("logs in with POST and keeps the bearer token out of browser storage", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      access_token: "test-token-with-minimum-length-123456789",
      runtime_instance_id: "runtime-instance-login-test",
      runtime_started_at: "2026-11-16T01:00:00+00:00",
      storage_persistence: "ephemeral",
    }), { status: 200, headers: { "Content-Type": "application/json" } })));
    render(<LoginGate><div>Protected</div></LoginGate>);
    fireEvent.change(screen.getByLabelText("Staging password"), { target: { value: "sixteen-plus-chars-for-staging" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(screen.getByText("Protected")).toBeInTheDocument());
    expect(getStagingToken()).toContain("test-token");
    expect(Array.from({ length: localStorage.length }, (_, i) => localStorage.getItem(localStorage.key(i) ?? ""))).not.toContain(getStagingToken());
  });

  it("does not accept an HTML fallback as server-confirmed logout", async () => {
    setStagingToken("current-session-token-of-sufficient-length");
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => Promise.resolve(
      url.endsWith("/auth/logout")
        ? new Response("<!doctype html>", { status: 200, headers: { "Content-Type": "text/html" } })
        : new Response(JSON.stringify({ authenticated: true }), { status: 200, headers: { "Content-Type": "application/json" } }),
    )));
    render(<SessionControls />);
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Unable to confirm logout"));
    expect(getStagingToken()).not.toBeNull();
  });

  it("keeps login usable when continuity storage is unavailable", async () => {
    vi.stubEnv("VITE_KANASU_STAGING_AUTH", "true");
    const storageSpy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("denied", "SecurityError");
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      access_token: "storage-failure-token-with-minimum-length-123456789",
      runtime_instance_id: "runtime-instance-storage-test",
      runtime_started_at: "2026-11-16T01:00:00+00:00",
      storage_persistence: "ephemeral",
    }), { status: 200, headers: { "Content-Type": "application/json" } })));
    render(<LoginGate><div>Protected after storage failure</div></LoginGate>);
    fireEvent.change(screen.getByLabelText("Staging password"), { target: { value: "sixteen-plus-chars-for-staging" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(screen.getByText("Protected after storage failure")).toBeInTheDocument());
    expect(getStagingToken()).toContain("storage-failure-token");
    storageSpy.mockRestore();
  });

  it("preserves supplied authorization and credentials outside staging", async () => {
    vi.stubEnv("VITE_KANASU_STAGING_AUTH", "false");
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }));
    vi.stubGlobal("fetch", fetchMock);
    await apiRequest("/backtest/config", {
      headers: { Authorization: "Bearer ordinary-local-token" },
      credentials: "include",
    }, "Unavailable");
    expect(fetchMock).toHaveBeenCalledWith("/api/backtest/config", expect.objectContaining({
      headers: { Authorization: "Bearer ordinary-local-token" },
      credentials: "include",
    }));
  });

  it("preserves the ordinary non-staging runtime status sidebar", () => {
    vi.stubEnv("VITE_KANASU_STAGING_AUTH", "false");
    render(<AppLayout><div>Page</div></AppLayout>);
    expect(screen.getByText("Runtime Status")).toBeInTheDocument();
    expect(screen.getByText("Connected")).toBeInTheDocument();
  });

  it("does not let a delayed old 401 erase a newer login", async () => {
    vi.stubEnv("VITE_KANASU_STAGING_AUTH", "true");
    let resolveOld: ((response: Response) => void) | undefined;
    const old = new Promise<Response>((resolve) => { resolveOld = resolve; });
    vi.stubGlobal("fetch", vi.fn().mockReturnValueOnce(old));
    setStagingToken("old-session-token-of-sufficient-length");
    const request = apiRequest("/backtest/config", undefined, "Unavailable");
    const rejection = expect(request).rejects.toMatchObject({ code: "session_expired" });
    setStagingToken("new-session-token-of-sufficient-length");
    await act(async () => { resolveOld!(new Response(null, { status: 401 })); await old; });
    await rejection;
    expect(getStagingToken()).toBe("new-session-token-of-sufficient-length");
  });
});
