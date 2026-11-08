import { Routes, Route } from "react-router-dom";

import { HomePage } from "./pages/HomePage";
import { PaperTradingPage } from "./pages/PaperTradingPage";
import { PortfolioPage } from "./pages/PortfolioPage";
import { ReplayPage } from "./pages/ReplayPage";
import { ResearchBacktestPage } from "./pages/ResearchBacktestPage";
import { ResearchPaperPage } from "./pages/ResearchPaperPage";
import { WfaPage } from "./pages/WfaPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/backtest" element={<ResearchBacktestPage />} />
      <Route path="/replay" element={<ReplayPage />} />
      <Route path="/wfa" element={<WfaPage />} />
      <Route path="/paper" element={<ResearchPaperPage />} />
      <Route path="/paper/standalone" element={<PaperTradingPage />} />
      <Route path="/portfolio" element={<PortfolioPage />} />
    </Routes>
  );
}
