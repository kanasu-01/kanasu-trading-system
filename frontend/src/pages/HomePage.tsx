import { useNavigate } from "react-router-dom";

import { AppLayout } from "@/app/AppLayout";

import { Card, CardContent } from "@/components/ui/card";

const pages = [
  {
    title: "Backtest",
    path: "/backtest",
    description: "Run and analyze strategy backtests",
  },

  {
    title: "Replay",
    path: "/replay",
    description: "Visualize and replay executions",
  },

  {
    title: "Paper Trading",
    path: "/paper",
    description: "Monitor paper trading runtime",
  },

  {
    title: "Portfolio",
    path: "/portfolio",
    description: "Coming soon - portfolio analytics",
  },
];

export function HomePage() {
  const navigate = useNavigate();

  return (
    <AppLayout>
      <div className="p-6">
        <div className="mb-8">
          <div
            className="
              text-3xl
              font-bold
              mb-2
            "
          >
            Kanasu Trading System
          </div>

          <div
            className="
              text-slate-400
            "
          >
            Quant Research & Trading Workspace
          </div>
        </div>

        <div
          className="
            grid
            grid-cols-1
            md:grid-cols-2
            xl:grid-cols-4
            gap-4
          "
        >
          {pages.map((page) => (
            <Card
              key={page.path}
              className="
                cursor-pointer
                hover:border-slate-600
                transition-colors
              "
              onClick={() => navigate(page.path)}
            >
              <CardContent className="p-5">
                <div
                  className="
                    text-lg
                    font-semibold
                    mb-2
                  "
                >
                  {page.title}
                </div>

                <div
                  className="
                    text-sm
                    text-slate-400
                  "
                >
                  {page.description}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </AppLayout>
  );
}
