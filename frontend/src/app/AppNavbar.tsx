// frontend/src/app/AppNavbar.tsx

import { NavLink } from "react-router-dom";

const linkStyle = {
  textDecoration: "none",
  padding: "6px 12px",
  borderRadius: 6,
  color: "#cbd5e1",
  fontSize: 14,
};

export function AppNavbar() {
  return (
    <div
      style={{
        display: "flex",
        gap: 8,
      }}
    >
      <NavLink
        to="/backtest"
        style={({ isActive }) => ({
          ...linkStyle,

          background: isActive ? "#1e293b" : "transparent",
        })}
      >
        Backtest
      </NavLink>

      <NavLink
        to="/paper"
        style={({ isActive }) => ({
          ...linkStyle,

          background: isActive ? "#1e293b" : "transparent",
        })}
      >
        Paper Trading
      </NavLink>

      <NavLink
        to="/portfolio"
        style={({ isActive }) => ({
          ...linkStyle,

          background: isActive ? "#1e293b" : "transparent",
        })}
      >
        Portfolio
      </NavLink>
    </div>
  );
}
