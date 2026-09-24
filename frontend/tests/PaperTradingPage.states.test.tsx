import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import {
  MemoryRouter,
} from "react-router-dom";
import {
  afterEach,
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
  session_id: "paper-state-1",
  status: "RUNNING",
  strategy_name:
    "SMACrossOver",
  symbol: "RELIANCE",
  started_at:
    "2025-05-20T09:15:00+05:30",
  stopped_at: null,
  initial_capital: 100000,
  cash: 98765.5,
  position_size: 10,
  position_value: 1234.5,
  equity: 100250.5,
  realized_pnl: 150,
  unrealized_pnl: 100.5,
  total_pnl: 250.5,
  peak_equity: 100300,
  drawdown: 49.5,
  active_position: {
    symbol: "RELIANCE",
    direction: "LONG",
    quantity: 10,
    entry_time:
      "2025-05-20T09:30:00+05:30",
    entry_price: 123.45,
    stop_price: 120,
  },
  completed_trade_count: 2,
  last_execution_event:
    "ENTRY_ACCEPTED",
  last_execution_price: 123.45,
  last_execution_quantity: 10,
  failure_type: null,
  failure_message: null,
};

const stoppedSnapshot:
PaperTradingSnapshot = {
  ...runningSnapshot,
  status: "STOPPED",
  stopped_at:
    "2025-05-20T10:00:00+05:30",
};

const failedSnapshot:
PaperTradingSnapshot = {
  ...runningSnapshot,
  status: "FAILED",
  stopped_at:
    "2025-05-20T10:00:00+05:30",
  failure_type:
    "ConnectionError",
  failure_message:
    "provider disconnected",
};

function renderPage() {
  render(
    <MemoryRouter
      initialEntries={[
        "/paper",
      ]}
    >
      <PaperTradingPage />
    </MemoryRouter>,
  );
}

describe(
  "PaperTradingPage application states",
  () => {
    beforeEach(() => {
      vi.clearAllMocks();

      getConfigMock.mockResolvedValue(
        config,
      );

      getStatusMock.mockResolvedValue({
        active: false,
        snapshot: null,
      });

      startMock.mockResolvedValue(
        runningSnapshot,
      );

      stopMock.mockResolvedValue(
        stoppedSnapshot,
      );
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it(
      "shows configuration loading state",
      () => {
        getConfigMock.mockReturnValueOnce(
          new Promise<
            PaperTradingConfigResponse
          >(() => void 0),
        );

        renderPage();

        expect(
          screen.getByText(
            "Loading paper trading application state...",
          ),
        ).toBeInTheDocument();
      },
    );
    it(
      "renders the no-session state",
      async () => {
        renderPage();

        expect(
          await screen.findByText(
            "NO SESSION",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByRole(
            "button",
            {
              name:
                "Start Paper Trading",
            },
          ),
        ).toBeEnabled();

        expect(
          screen.getByRole(
            "button",
            {
              name:
                "Stop Session",
            },
          ),
        ).toBeDisabled();
      },
    );

    it(
      "renders authoritative running account, position, and execution state",
      async () => {
        getStatusMock.mockResolvedValue({
          active: true,
          snapshot:
            runningSnapshot,
        });

        renderPage();

        expect(
          await screen.findByText(
            "paper-state-1",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            "ENTRY_ACCEPTED",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            "2025-05-20T09:30:00+05:30",
          ),
        ).toBeInTheDocument();

        const cash =
          new Intl.NumberFormat(
            "en-IN",
            {
              maximumFractionDigits: 2,
            },
          ).format(
            98765.5,
          );

        const equity =
          new Intl.NumberFormat(
            "en-IN",
            {
              maximumFractionDigits: 2,
            },
          ).format(
            100250.5,
          );

        expect(
          screen.getByText(cash),
        ).toBeInTheDocument();

        expect(
          screen.getByText(equity),
        ).toBeInTheDocument();

        expect(
          screen.getByRole(
            "button",
            {
              name:
                "Stop Session",
            },
          ),
        ).toBeEnabled();
      },
    );

    it(
      "retains a terminal stopped snapshot",
      async () => {
        getStatusMock.mockResolvedValue({
          active: false,
          snapshot:
            stoppedSnapshot,
        });

        renderPage();

        expect(
          await screen.findByText(
            "STOPPED",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            "paper-state-1",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByRole(
            "button",
            {
              name:
                "Start Paper Trading",
            },
          ),
        ).toBeEnabled();

        expect(
          screen.getByRole(
            "button",
            {
              name:
                "Stop Session",
            },
          ),
        ).toBeDisabled();
      },
    );

    it(
      "renders terminal runtime failure information",
      async () => {
        getStatusMock.mockResolvedValue({
          active: false,
          snapshot:
            failedSnapshot,
        });

        renderPage();

        expect(
          await screen.findByText(
            "FAILED",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            "ConnectionError",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            "provider disconnected",
          ),
        ).toBeInTheDocument();
      },
    );

    it(
      "shows start failure without inventing running state",
      async () => {
        startMock.mockRejectedValueOnce(
          new Error(
            "start unavailable",
          ),
        );

        renderPage();

        const startButton =
          await screen.findByRole(
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

        fireEvent.click(
          startButton,
        );

        expect(
          await screen.findByText(
            "start unavailable",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            "NO SESSION",
          ),
        ).toBeInTheDocument();
      },
    );

    it(
      "shows stop failure while preserving the running snapshot",
      async () => {
        getStatusMock.mockResolvedValue({
          active: true,
          snapshot:
            runningSnapshot,
        });

        stopMock.mockRejectedValueOnce(
          new Error(
            "stop unavailable",
          ),
        );

        renderPage();

        const stopButton =
          await screen.findByRole(
            "button",
            {
              name:
                "Stop Session",
            },
          );

        await waitFor(() => {
          expect(
            stopButton,
          ).toBeEnabled();
        });

        fireEvent.click(
          stopButton,
        );

        expect(
          await screen.findByText(
            "stop unavailable",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            "paper-state-1",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            "RUNNING",
          ),
        ).toBeInTheDocument();
      },
    );

    it(
      "polls while active and stops polling after terminal status",
      async () => {
        vi.useFakeTimers();

        getStatusMock.mockReset();

        getStatusMock
          .mockResolvedValueOnce({
            active: true,
            snapshot:
              runningSnapshot,
          })
          .mockResolvedValueOnce({
            active: false,
            snapshot:
              stoppedSnapshot,
          });

        renderPage();

        await act(
          async () => {
            await Promise.resolve();
            await Promise.resolve();
            await Promise.resolve();
          },
        );

        expect(
          screen.getByText(
            "RUNNING",
          ),
        ).toBeInTheDocument();

        expect(
          getStatusMock,
        ).toHaveBeenCalledTimes(1);

        await act(
          async () => {
            await vi.advanceTimersByTimeAsync(
              2000,
            );
          },
        );

        expect(
          screen.getByText(
            "STOPPED",
          ),
        ).toBeInTheDocument();

        expect(
          getStatusMock,
        ).toHaveBeenCalledTimes(2);

        await act(
          async () => {
            await vi.advanceTimersByTimeAsync(
              4000,
            );
          },
        );

        expect(
          getStatusMock,
        ).toHaveBeenCalledTimes(2);
      },
    );
  },
);
