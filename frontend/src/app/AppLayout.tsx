// frontend/src/app/AppLayout.tsx

import type { ReactNode } from "react";

import { AppNavbar } from "./AppNavbar";

type Props = {
  children: ReactNode;
};

export function AppLayout({ children }: Props) {
  return (
    <div
      style={{
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        background: "#020617",
        color: "#e2e8f0",
      }}
    >
      {/* TOP BAR */}
      <div
        style={{
          height: 52,

          borderBottom: "1px solid #1e293b",

          display: "flex",

          alignItems: "center",

          justifyContent: "space-between",

          paddingLeft: 16,
          paddingRight: 16,

          flexShrink: 0,
        }}
      >
        <strong>Kanasu Trading System</strong>

        <AppNavbar />
      </div>

      {/* BODY */}
      <div
        style={{
          flex: 1,
          display: "flex",
          minHeight: 0,
        }}
      >
        {/* SIDEBAR */}
        <div
          style={{
            width: 220,

            borderRight: "1px solid #1e293b",

            padding: 12,

            flexShrink: 0,
          }}
        >
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
        <div
          style={{
            flex: 1,
            minWidth: 0,
            minHeight: 0,
          }}
        >
          {children}
        </div>
      </div>
    </div>
  );
}
