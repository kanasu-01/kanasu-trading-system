// frontend/src/app/AppLayout.tsx

import type { ReactNode } from "react";

import { AppNavbar } from "./AppNavbar";

type Props = {
  children: ReactNode;
};

export function AppLayout({ children }: Props) {
  return (
    <div className="flex h-screen flex-col bg-slate-950 text-slate-200">
      {/* TOP BAR */}
      <div className="flex min-h-[52px] flex-shrink-0 flex-wrap items-center justify-between gap-2 border-b border-slate-800 px-4 py-2">
        <strong>Kanasu Trading System</strong>

        <AppNavbar />
      </div>

      {/* BODY */}
      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        {/* SIDEBAR */}
        <div className="w-full flex-shrink-0 border-b border-slate-800 p-3 md:w-[220px] md:border-b-0 md:border-r">
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
        </div>

        {/* PAGE CONTENT */}
        <div className="min-h-0 min-w-0 flex-1 overflow-auto">
          {children}
        </div>
      </div>
    </div>
  );
}
