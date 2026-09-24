import {
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import {
  MemoryRouter,
} from "react-router-dom";
import {
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import {
  getBacktestConfig,
  runBacktest,
} from "@/api/backtestApi";
import {
  BacktestPage,
} from "@/pages/BacktestPage";

import type {
  BacktestConfigResponse,
  BacktestRunResponse,
} from "@/types/backtest";

vi.mock(
  "@/api/backtestApi",
  () => ({
    getBacktestConfig: vi.fn(),
    runBacktest: vi.fn(),
  }),
);

const getConfigMock =
  vi.mocked(getBacktestConfig);

const runBacktestMock =
  vi.mocked(runBacktest);

const config:
BacktestConfigResponse = {
  markets: [
    {
      id: "NSE",
      name: "NSE",
    },
  ],
  symbols: [
    {
      symbol: "RELIANCE",
      exchange: "NSE",
    },
  ],
  timeframes: [
    {
      id: "15m",
      label: "15 Minutes",
    },
  ],
  strategies: [
    {
      id: "sma_crossover",
      name: "SMA Crossover",
    },
  ],
  timezones: [
    "Asia/Kolkata",
  ],
};

const result:
BacktestRunResponse = {
  run_id: "run-state-1",
  status: "completed",
  symbol: "RELIANCE",
  timeframe: "15m",
  strategy_id: "sma_crossover",
  start:
    "2025-05-01T09:15:00+05:30",
  end:
    "2025-05-20T15:30:00+05:30",
  timezone: "Asia/Kolkata",
  summary: {
    completed_trade_count: 1,
    net_profitable_trade_count: 1,
    net_losing_trade_count: 0,
    net_breakeven_trade_count: 0,
    net_profitable_trade_rate_pct: 100,
    mean_positive_instrument_return_pct: 2.6,
    mean_negative_instrument_return_pct: 0,
    mean_instrument_return_pct: 2.6,
    gross_realized_pnl: 260,
    net_realized_pnl: 240,
    mean_net_pnl_per_completed_trade: 240,
    completed_trade_transaction_cost_total: 20,
    account_pnl: 250.5,
    account_return_pct: 0.2505,
    max_equity_drawdown_pct: 0.1,
  },
  equity_curve: [
    {
      timestamp:
        "2025-05-01T09:15:00+05:30",
      equity: 100250.5,
    },
  ],
  trades: [
    {
      symbol: "RELIANCE",
      entry_time:
        "2025-05-01T09:30:00+05:30",
      entry_price: 100,
      exit_time:
        "2025-05-01T10:00:00+05:30",
      exit_price: 102.6,
      stop_price: 98,
      quantity: 10,
      direction: "LONG",
      exit_reason: "STRATEGY_EXIT",
      net_pnl: 240,
      gross_pnl: 260,
      transaction_cost: 20,
      instrument_return_pct: 2.6,
    },
  ],
};

function renderPage() {
  render(
    <MemoryRouter
      initialEntries={[
        "/backtest",
      ]}
    >
      <BacktestPage />
    </MemoryRouter>,
  );
}

async function submitBacktest() {
  await screen.findByText(
    "Backtest Workspace",
  );

  fireEvent.change(
    screen.getByLabelText(
      "Backtest start",
    ),
    {
      target: {
        value:
          "2025-05-01T09:15",
      },
    },
  );

  fireEvent.change(
    screen.getByLabelText(
      "Backtest end",
    ),
    {
      target: {
        value:
          "2025-05-20T15:30",
      },
    },
  );

  const runButton =
    screen.getByRole(
      "button",
      {
        name: "Run Backtest",
      },
    );

  await waitFor(() => {
    expect(
      runButton,
    ).toBeEnabled();
  });

  fireEvent.click(runButton);
}

describe(
  "BacktestPage application states",
  () => {
    beforeEach(() => {
      vi.clearAllMocks();

      getConfigMock.mockResolvedValue(
        config,
      );

      runBacktestMock.mockResolvedValue(
        result,
      );
    });

    it(
      "shows configuration loading state",
      () => {
        getConfigMock.mockReturnValueOnce(
          new Promise<
            BacktestConfigResponse
          >(() => void 0),
        );

        renderPage();

        expect(
          screen.getByText(
            "Loading backtest configuration...",
          ),
        ).toBeInTheDocument();
      },
    );

    it(
      "shows in-flight execution state",
      async () => {
        runBacktestMock.mockReturnValueOnce(
          new Promise<
            BacktestRunResponse
          >(() => void 0),
        );

        renderPage();

        await submitBacktest();

        expect(
          await screen.findByRole(
            "button",
            {
              name: "Running...",
            },
          ),
        ).toBeDisabled();

        expect(
          screen.getByText(
            "Running backtest...",
          ),
        ).toBeInTheDocument();
      },
    );
    it(
      "shows configuration failure",
      async () => {
        getConfigMock.mockRejectedValueOnce(
          new Error(
            "configuration unavailable",
          ),
        );

        renderPage();

        expect(
          await screen.findByText(
            "configuration unavailable",
          ),
        ).toBeInTheDocument();
      },
    );

    it(
      "shows execution failure and restores controls",
      async () => {
        runBacktestMock.mockRejectedValueOnce(
          new Error(
            "execution unavailable",
          ),
        );

        renderPage();

        await submitBacktest();

        expect(
          await screen.findByText(
            "execution unavailable",
          ),
        ).toBeInTheDocument();

        await waitFor(() => {
          expect(
            screen.getByRole(
              "button",
              {
                name:
                  "Run Backtest",
              },
            ),
          ).toBeEnabled();
        });
      },
    );

    it(
      "renders authoritative non-empty result projections",
      async () => {
        renderPage();

        await submitBacktest();

        expect(
          await screen.findByText(
            "run-state-1",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            "STRATEGY_EXIT",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getAllByText(
            "2025-05-01T09:15:00+05:30",
          ),
        ).toHaveLength(2);

        const formattedEquity =
          new Intl.NumberFormat(
            "en-IN",
            {
              maximumFractionDigits: 2,
            },
          ).format(
            100250.5,
          );

        expect(
          screen.getByText(
            formattedEquity,
          ),
        ).toBeInTheDocument();
      },
    );
  },
);
