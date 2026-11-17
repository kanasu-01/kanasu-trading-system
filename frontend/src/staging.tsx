import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { API_BASE_URL } from "@/api/apiClient";
import { getStagingToken, recordStagingRuntime, setStagingToken, subscribeStagingSession } from "@/stagingSession";

function metadata(value: unknown): value is Record<string, string> {
  if (typeof value !== "object" || value === null) return false;
  const x = value as Record<string, unknown>;
  return typeof x.runtime_instance_id === "string" && x.runtime_instance_id.length >= 16
    && typeof x.runtime_started_at === "string" && x.storage_persistence === "ephemeral";
}

export function LoginGate({ children }: { children: ReactNode }) {
  const [, redraw] = useState(0);
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => subscribeStagingSession(() => redraw((x) => x + 1)), []);

  async function submit(event: FormEvent) {
    event.preventDefault(); setPending(true); setMessage(null);
    try {
      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }), credentials: "omit", cache: "no-store",
      });
      if (!response.ok) throw new Error(response.status === 429 ? "Too many login attempts. Try later." : response.status === 503 ? "Staging login is unavailable." : "Incorrect password or login failed.");
      const payload: unknown = await response.json();
      if (typeof payload !== "object" || payload === null || !("access_token" in payload)
        || typeof payload.access_token !== "string" || payload.access_token.length < 32 || !metadata(payload)) {
        throw new Error("The backend returned an invalid login response.");
      }
      recordStagingRuntime(payload as Record<string, string>);
      setPassword(""); setStagingToken(payload.access_token);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to connect to Kanasu.");
    } finally { setPending(false); }
  }

  if (getStagingToken()) return <>{children}</>;
  return <main className="flex min-h-screen items-center justify-center bg-slate-950 p-6 text-slate-200">
    <form className="w-full max-w-md space-y-5 rounded-xl border border-slate-700 bg-slate-900 p-8" onSubmit={(event) => { void submit(event); }}>
      <h1 className="text-2xl font-semibold">Kanasu staging login</h1>
      <p className="text-sm text-slate-400">Sign in to use Backtest, Research, and Paper Trading. No real orders are allowed.</p>
      <label className="block space-y-2"><span>Staging password</span><input type="password" required minLength={16} maxLength={4096} value={password} onChange={(e) => setPassword(e.target.value)} className="w-full rounded-md border border-slate-600 bg-slate-950 px-3 py-2" /></label>
      {message && <p role="alert" className="text-red-400">{message}</p>}
      <button className="rounded-md bg-blue-700 px-5 py-2 font-medium disabled:opacity-50" disabled={pending} type="submit">{pending ? "Signing in…" : "Sign in"}</button>
    </form>
  </main>;
}

export function SessionControls() {
  const [status, setStatus] = useState("Checking…");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    async function check() {
      const current = getStagingToken();
      if (!current) { if (!cancelled) setStatus("Disconnected"); return; }
      try {
        const response = await fetch(`${API_BASE_URL}/auth/session`, { headers: { Authorization: `Bearer ${current}` }, credentials: "omit", cache: "no-store" });
        if (cancelled || getStagingToken() !== current) return;
        if (response.status === 401 || response.status === 403) { setStagingToken(null); return; }
        const type = response.headers.get("content-type")?.toLowerCase() ?? "";
        const payload: unknown = type.includes("application/json") ? await response.json() : null;
        setStatus(response.ok && typeof payload === "object" && payload !== null && "authenticated" in payload && payload.authenticated === true ? "Connected" : "Disconnected");
      } catch { if (!cancelled && getStagingToken() === current) setStatus("Disconnected"); }
    }
    void check(); const timer = window.setInterval(() => { void check(); }, 60_000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, []);

  async function logout() {
    const current = getStagingToken(); if (!current) return; setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/auth/logout`, { method: "POST", headers: { Authorization: `Bearer ${current}` }, credentials: "omit", cache: "no-store" });
      const type = response.headers.get("content-type")?.toLowerCase() ?? "";
      const payload: unknown = type.includes("application/json") ? await response.json() : null;
      const confirmed = response.status === 401 || (response.ok && typeof payload === "object" && payload !== null && "signed_out" in payload && payload.signed_out === true);
      if (!confirmed) throw new Error();
      if (getStagingToken() === current) setStagingToken(null);
    } catch { setError("Unable to confirm logout. Please retry."); }
  }

  return <div className="space-y-3"><div className="text-sm text-slate-400">Backend API Status</div><div className="text-sm">{status}</div><button className="rounded-md border border-slate-600 px-3 py-2 text-sm" onClick={() => { void logout(); }} type="button">Sign out</button>{error && <p role="alert" className="text-xs text-red-400">{error}</p>}</div>;
}
