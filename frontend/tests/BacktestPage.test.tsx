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
  run_id: "run-1",
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
    completed_trade_count: 0,
    net_profitable_trade_count: 0,
    net_losing_trade_count: 0,
    net_breakeven_trade_count: 0,
    net_profitable_trade_rate_pct: 0,
    mean_positive_instrument_return_pct: 0,
    mean_negative_instrument_return_pct: 0,
    mean_instrument_return_pct: 0,
    gross_realized_pnl: 0,
    net_realized_pnl: 0,
    mean_net_pnl_per_completed_trade: 0,
    completed_trade_transaction_cost_total: 0,
    account_pnl: 0,
    account_return_pct: 0,
    max_equity_drawdown_pct: 0,
  },
  equity_curve: [],
  trades: [],
};

describe("BacktestPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    getConfigMock.mockResolvedValue(
      config,
    );

    runBacktestMock.mockResolvedValue(
      result,
    );
  });

  it("submits the authoritative request and renders the response", async () => {
    render(
      <MemoryRouter
        initialEntries={[
          "/backtest",
        ]}
      >
        <BacktestPage />
      </MemoryRouter>,
    );

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

    await waitFor(() => {
      expect(
        runBacktestMock,
      ).toHaveBeenCalledWith({
        symbol: "RELIANCE",
        timeframe: "15m",
        strategy_id:
          "sma_crossover",
        start:
          "2025-05-01T09:15:00+05:30",
        end:
          "2025-05-20T15:30:00+05:30",
        timezone:
          "Asia/Kolkata",
        initial_capital:
          100000,
        strategy_params: {
          fast_period: 20,
          slow_period: 50,
        },
      });
    });

    expect(
      await screen.findByText(
        "run-1",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        "No equity points were returned.",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        "No completed trades were produced for this run.",
      ),
    ).toBeInTheDocument();
  });
});
