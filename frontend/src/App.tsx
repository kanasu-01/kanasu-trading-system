import { BacktestPage } from "./pages/BacktestPage";

import { Routes, Route } from "react-router-dom";

import { ReplayPage } from "./pages/ReplayPage";

import { PaperTradingPage } from "./pages/PaperTradingPage";

import { PortfolioPage } from "./pages/PortfolioPage";
import { HomePage } from "./pages/HomePage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />

      <Route path="/backtest" element={<BacktestPage />} />

      <Route path="/replay" element={<ReplayPage />} />

      <Route path="/paper" element={<PaperTradingPage />} />

      <Route path="/portfolio" element={<PortfolioPage />} />
    </Routes>
  );
}
