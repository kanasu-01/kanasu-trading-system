import { Routes, Route, Navigate } from "react-router-dom";

import { BacktestPage } from "./pages/BacktestPage";

import { PaperTradingPage } from "./pages/PaperTradingPage";

import { PortfolioPage } from "./pages/PortfolioPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/backtest" replace />} />

      <Route path="/backtest" element={<BacktestPage />} />

      <Route path="/paper" element={<PaperTradingPage />} />

      <Route path="/portfolio" element={<PortfolioPage />} />
    </Routes>
  );
}
