import type { ReactNode } from "react";

import { AppNavbar } from "./AppNavbar";
import { SessionControls } from "@/staging";
import { stagingContinuityNotice, stagingFrontend } from "@/stagingSession";

type Props = {
  children: ReactNode;
};

export function AppLayout({ children }: Props) {
  const continuityNotice = stagingFrontend()
    ? stagingContinuityNotice()
    : null;

  return (
    <div className="flex h-screen flex-col bg-slate-950 text-slate-200">
      {/* TOP BAR */}
      <div className="flex min-h-[52px] flex-shrink-0 flex-wrap items-center justify-between gap-2 border-b border-slate-800 px-4 py-2">
        <strong>Kanasu Trading System</strong>

        <AppNavbar />
      </div>

      {continuityNotice && (
        <div
          className="border-b border-amber-800 bg-amber-950/40 px-4 py-2 text-sm text-amber-200"
          role="status"
        >
          {continuityNotice}
        </div>
      )}

      {/* BODY */}
      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        {/* SIDEBAR */}
        <div className="w-full flex-shrink-0 border-b border-slate-800 p-3 md:w-[220px] md:border-b-0 md:border-r">
          {stagingFrontend() ? (
            <SessionControls />
          ) : (
            <>
              <div
                style={{
                  fontSize: 13,
                  opacity: 0.7,
                  marginBottom: 12,
                }}
              >
                Runtime Status
              </div>

              <div
                style={{
                  fontSize: 14,
                }}
              >
                Connected
              </div>
            </>
          )}
        </div>

        {/* PAGE CONTENT */}
        <div className="min-h-0 min-w-0 flex-1 overflow-auto">
          {children}
        </div>
      </div>
    </div>
  );
}
