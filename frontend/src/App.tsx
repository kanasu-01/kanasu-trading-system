import { Routes, Route } from "react-router-dom";

import { LoginGate } from "./staging";
import { stagingFrontend } from "./stagingSession";
import { BacktestPage } from "./pages/BacktestPage";
import { ReplayPage } from "./pages/ReplayPage";
import { PaperTradingPage } from "./pages/PaperTradingPage";
import { PortfolioPage } from "./pages/PortfolioPage";
import { HomePage } from "./pages/HomePage";

export default function App() {
  const pages = (
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/backtest" element={<BacktestPage />} />
        <Route path="/replay" element={<ReplayPage />} />
        <Route path="/paper" element={<PaperTradingPage />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
      </Routes>
  );

  return stagingFrontend() ? (
    <LoginGate>{pages}</LoginGate>
  ) : pages;
}
