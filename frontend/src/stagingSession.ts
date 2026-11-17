let token: string | null = null;
const listeners = new Set<() => void>();
const RUNTIME_KEY = "kanasu.staging.runtime_instance_id";
const NOTICE_KEY = "kanasu.staging.continuity_notice";

export function stagingFrontend(): boolean {
  return import.meta.env.VITE_KANASU_STAGING_AUTH === "true";
}

export function getStagingToken(): string | null {
  return token;
}

export function setStagingToken(value: string | null): void {
  if (token === value) return;
  token = value;
  listeners.forEach((listener) => listener());
}

export function subscribeStagingSession(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function recordStagingRuntime(value: Record<string, string>): void {
  const prior = window.localStorage.getItem(RUNTIME_KEY);
  let notice: string | null = null;
  if (prior === null) {
    notice = "Backend continuity cannot be established from this browser. Temporary staging storage is disposable, so earlier Paper Trading runtime or local staging data may be unavailable.";
  } else if (prior !== value.runtime_instance_id) {
    notice = "The staging backend restarted or was replaced. In-memory Paper Trading state from the previous backend instance cannot continue, and disposable local staging data may have been lost.";
  }
  window.localStorage.setItem(RUNTIME_KEY, value.runtime_instance_id);
  if (notice) window.localStorage.setItem(NOTICE_KEY, notice);
  else window.localStorage.removeItem(NOTICE_KEY);
}

export function stagingContinuityNotice(): string | null {
  return window.localStorage.getItem(NOTICE_KEY);
}
