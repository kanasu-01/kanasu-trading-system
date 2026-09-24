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
  getPaperTradingConfig,
  getPaperTradingStatus,
  startPaperTrading,
  stopPaperTrading,
} from "@/api/paperTradingApi";
import {
  PaperTradingPage,
} from "@/pages/PaperTradingPage";

import type {
  PaperTradingConfigResponse,
  PaperTradingSnapshot,
} from "@/types/paperTrading";

vi.mock(
  "@/api/paperTradingApi",
  () => ({
    getPaperTradingConfig:
      vi.fn(),
    getPaperTradingStatus:
      vi.fn(),
    startPaperTrading:
      vi.fn(),
    stopPaperTrading:
      vi.fn(),
  }),
);

const getConfigMock =
  vi.mocked(
    getPaperTradingConfig,
  );

const getStatusMock =
  vi.mocked(
    getPaperTradingStatus,
  );

const startMock =
  vi.mocked(
    startPaperTrading,
  );

const stopMock =
  vi.mocked(
    stopPaperTrading,
  );

const config:
PaperTradingConfigResponse = {
  symbols: [
    {
      symbol: "RELIANCE",
      exchange: "NSE",
    },
  ],
  strategies: [
    {
      id: "sma_crossover",
      name: "SMA Crossover",
    },
  ],
};

const runningSnapshot:
PaperTradingSnapshot = {
  session_id: "session-1",
  status: "RUNNING",
  strategy_name:
    "sma_crossover",
  symbol: "RELIANCE",
  started_at:
    "2025-05-20T09:15:00+05:30",
  stopped_at: null,
  initial_capital: 100000,
  cash: 100000,
  position_size: 0,
  position_value: 0,
  equity: 100000,
  realized_pnl: 0,
  unrealized_pnl: 0,
  total_pnl: 0,
  peak_equity: 100000,
  drawdown: 0,
  active_position: null,
  completed_trade_count: 0,
  last_execution_event: null,
  last_execution_price: null,
  last_execution_quantity: null,
  failure_type: null,
  failure_message: null,
};

describe("PaperTradingPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    getConfigMock.mockResolvedValue(
      config,
    );

    getStatusMock
      .mockResolvedValueOnce({
        active: false,
        snapshot: null,
      })
      .mockRejectedValueOnce(
        new Error(
          "status unavailable",
        ),
      )
      .mockResolvedValue({
        active: true,
        snapshot:
          runningSnapshot,
      });

    startMock.mockResolvedValue(
      runningSnapshot,
    );

    stopMock.mockResolvedValue({
      ...runningSnapshot,
      status: "STOPPED",
      stopped_at:
        "2025-05-20T10:00:00+05:30",
    });
  });

  it("retains the start snapshot when the immediate status refresh fails", async () => {
    render(
      <MemoryRouter
        initialEntries={[
          "/paper",
        ]}
      >
        <PaperTradingPage />
      </MemoryRouter>,
    );

    await screen.findByText(
      "Paper Trading Runtime",
    );

    const startButton =
      screen.getByRole(
        "button",
        {
          name:
            "Start Paper Trading",
        },
      );

    await waitFor(() => {
      expect(
        startButton,
      ).toBeEnabled();
    });

    fireEvent.click(startButton);

    expect(
      await screen.findByText(
        "session-1",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        "status unavailable",
      ),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(
        screen.getByRole(
          "button",
          {
            name:
              "Stop Session",
          },
        ),
      ).toBeEnabled();
    });

    expect(
      startMock,
    ).toHaveBeenCalledWith({
      symbol: "RELIANCE",
      strategy_id:
        "sma_crossover",
    });
  });
});
