import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiRequestError } from "@/api/apiClient";
import {
  createWorkspaceStudy,
  getResearchWorkspaceConfig,
  getWorkspaceBacktestResult,
  getWorkspaceStrategies,
  qualifyWorkspaceStudy,
  retryWorkspaceBacktest,
  runWorkspaceBacktest,
} from "@/api/researchWorkspaceApi";
import { ResearchBacktestPage } from "@/pages/ResearchBacktestPage";


function installRadixSelectDomStubs() {
  Object.defineProperty(HTMLElement.prototype, "hasPointerCapture", {
    configurable: true,
    value: () => false,
  });
  Object.defineProperty(HTMLElement.prototype, "setPointerCapture", {
    configurable: true,
    value: () => undefined,
  });
  Object.defineProperty(HTMLElement.prototype, "releasePointerCapture", {
    configurable: true,
    value: () => undefined,
  });
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
    configurable: true,
    value: () => undefined,
  });
}

vi.mock("@/api/researchWorkspaceApi", () => ({
  createWorkspaceStudy: vi.fn(),
  getResearchWorkspaceConfig: vi.fn(),
  getWorkspaceBacktestResult: vi.fn(),
  getWorkspaceStrategies: vi.fn(),
  qualifyWorkspaceStudy: vi.fn(),
  retryWorkspaceBacktest: vi.fn(),
  runWorkspaceBacktest: vi.fn(),
}));

const config = {
  markets: [{ id: "NSE", name: "NSE" }],
  symbols: [
    { symbol: "RELIANCE", exchange: "NSE" },
    { symbol: "TCS", exchange: "NSE" },
  ],
  timeframes: [{ id: "15m", label: "15 Minutes" }],
  strategies: [{ id: "sma_crossover", name: "SMA Crossover" }],
  timezones: ["Asia/Kolkata"],
  studies: [
    {
      study_id: "study-1",
      display_title: "SMA Research",
      created_at: "2026-11-07T00:00:00Z",
      archived: false,
    },
  ],
  active_qualification_policy: {
    policy_id: "policy-1",
    version: 1,
    threshold_pct: "50",
  },
};

const savedResult = {
  run_id: "run-1",
  attempt_id: "attempt-1",
  evidence_id: "evidence-1",
  evidence_status: "ACCEPTED" as const,
  status: "completed" as const,
  symbol: "RELIANCE",
  timeframe: "15m",
  strategy_id: "sma_crossover",
  start: "2026-01-05T09:15:00+05:30",
  end: "2026-01-05T10:45:00+05:30",
  timezone: "Asia/Kolkata",
  summary: {
    completed_trade_count: 1,
    net_profitable_trade_count: 1,
    net_losing_trade_count: 0,
    net_breakeven_trade_count: 0,
    net_profitable_trade_rate_pct: 100,
    mean_positive_instrument_return_pct: 1,
    mean_negative_instrument_return_pct: 0,
    mean_instrument_return_pct: 1,
    gross_realized_pnl: 100,
    net_realized_pnl: 90,
    mean_net_pnl_per_completed_trade: 90,
    completed_trade_transaction_cost_total: 10,
    account_pnl: 90,
    account_return_pct: 0.09,
    max_equity_drawdown_pct: 0,
  },
  equity_curve: [],
  trades: [],
  study_id: "study-1",
  study_revision_id: "sha256:" + "1".repeat(64),
  trial_id: "sha256:" + "2".repeat(64),
};

const strategies = {
  study_id: "study-1",
  strategies: [
    {
      study_id: "study-1",
      study_revision_id: "sha256:" + "1".repeat(64),
      revision_number: 1,
      trial_id: "sha256:" + "2".repeat(64),
      instrument_id: "NSE-EQ-RELIANCE",
      symbol: "RELIANCE",
      timeframe: "15m",
      strategy_procedure_id: "sma-crossover-v1",
      strategy_label: "SMA Crossover 20/50",
      strategy_parameters: { fast_period: 20, slow_period: 50 },
      trial_disposition: "EXECUTED",
      trial_disposition_event_id: "trial-event-1",
      qualification_outcome: null,
      qualification_decision_id: null,
      candidate_revision_id: null,
      wfa_outcome: null,
      wfa_verdict: null,
      wfa_decision_id: null,
      paper_campaign_id: null,
      retryable: false,
    },
  ],
};

describe("ResearchBacktestPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    installRadixSelectDomStubs();
    vi.mocked(getResearchWorkspaceConfig).mockResolvedValue(config);
    vi.mocked(getWorkspaceStrategies).mockResolvedValue(strategies);
    vi.mocked(getWorkspaceBacktestResult).mockResolvedValue(savedResult);
    vi.mocked(createWorkspaceStudy).mockResolvedValue(config.studies[0]);
    vi.mocked(retryWorkspaceBacktest).mockResolvedValue(strategies.strategies[0]);
    vi.mocked(qualifyWorkspaceStudy).mockResolvedValue({
      study_id: "study-1",
      policy: config.active_qualification_policy,
      policy_changed: false,
      policy_current: true,
      results: [],
    });
  });

  it("uses the selected Study and canonical symbol for one registered Backtest", async () => {
    vi.mocked(runWorkspaceBacktest).mockResolvedValue(savedResult);

    render(
      <MemoryRouter>
        <ResearchBacktestPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("SMA Research")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Backtest start"), {
      target: { value: "2026-01-05T09:15" },
    });
    fireEvent.change(screen.getByLabelText("Backtest end"), {
      target: { value: "2026-01-05T10:45" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Start Backtest" }));

    await waitFor(() => {
      expect(runWorkspaceBacktest).toHaveBeenCalledWith(
        expect.objectContaining({
          study_id: "study-1",
          symbol: "RELIANCE",
          strategy_params: { fast_period: 20, slow_period: 50 },
        }),
      );
    });
  });

  it("warns when the global qualification threshold changes", async () => {
    render(
      <MemoryRouter>
        <ResearchBacktestPage />
      </MemoryRouter>,
    );
    await screen.findByText(/SMA Crossover 20\/50/);
    fireEvent.click(
      screen.getByRole("button", { name: "Send Strategies to WFA" }),
    );
    fireEvent.change(screen.getByLabelText("Qualification threshold"), {
      target: { value: "60" },
    });
    expect(
      screen.getByText(/creates a new policy version/i),
    ).toBeInTheDocument();
  });

  it("refreshes stale global policy before allowing a different threshold", async () => {
    const refreshed = {
      ...config,
      active_qualification_policy: {
        policy_id: "policy-2",
        version: 2,
        threshold_pct: "60",
      },
    };
    vi.mocked(getResearchWorkspaceConfig)
      .mockResolvedValueOnce(config)
      .mockResolvedValueOnce(refreshed);
    vi.mocked(qualifyWorkspaceStudy).mockRejectedValueOnce(
      new ApiRequestError(
        409,
        "qualification_policy_conflict",
        "Qualification policy could not be changed safely",
      ),
    );

    render(
      <MemoryRouter>
        <ResearchBacktestPage />
      </MemoryRouter>,
    );

    await screen.findByText(/SMA Crossover 20\/50/);
    fireEvent.click(
      screen.getByRole("button", { name: "Send Strategies to WFA" }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Apply and Send" }),
    );

    await waitFor(() => {
      expect(qualifyWorkspaceStudy).toHaveBeenCalledWith(
        "study-1",
        "50",
        "policy-1",
      );
    });
    expect(
      await screen.findByText(/changed since this page loaded/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/from 60% to 50%/i),
    ).toBeInTheDocument();
  });


  it("submits a null observed policy when no active policy exists", async () => {
    const noPolicyConfig = {
      ...config,
      active_qualification_policy: null,
    };
    vi.mocked(getResearchWorkspaceConfig).mockResolvedValueOnce(noPolicyConfig);
    vi.mocked(qualifyWorkspaceStudy).mockResolvedValueOnce({
      study_id: "study-1",
      policy: {
        policy_id: "policy-1",
        version: 1,
        threshold_pct: "50",
      },
      policy_changed: true,
      policy_current: true,
      results: [],
    });

    render(
      <MemoryRouter>
        <ResearchBacktestPage />
      </MemoryRouter>,
    );

    await screen.findByText(/SMA Crossover 20\/50/);
    fireEvent.click(
      screen.getByRole("button", { name: "Send Strategies to WFA" }),
    );
    fireEvent.change(screen.getByLabelText("Qualification threshold"), {
      target: { value: "50" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Apply and Send" }),
    );

    await waitFor(() => {
      expect(qualifyWorkspaceStudy).toHaveBeenCalledWith(
        "study-1",
        "50",
        null,
      );
    });
  });

  it("does not let an older Study strategy read overwrite a newly created Study", async () => {
    let resolveOld!: (value: typeof strategies) => void;
    const oldRead = new Promise<typeof strategies>((resolve) => {
      resolveOld = resolve;
    });
    const priorStudy = {
      study_id: "study-2",
      display_title: "Prior Study",
      created_at: "2026-11-07T00:01:00Z",
      archived: false,
    };
    const newStudy = {
      study_id: "study-3",
      display_title: "New Study",
      created_at: "2026-11-07T00:02:00Z",
      archived: false,
    };
    const configBeforeCreate = {
      ...config,
      studies: [...config.studies, priorStudy],
    };
    const configAfterCreate = {
      ...configBeforeCreate,
      studies: [...configBeforeCreate.studies, newStudy],
    };

    vi.mocked(getResearchWorkspaceConfig)
      .mockResolvedValueOnce(configBeforeCreate)
      .mockResolvedValueOnce(configAfterCreate);
    vi.mocked(getWorkspaceStrategies)
      .mockResolvedValueOnce(strategies)
      .mockReturnValueOnce(oldRead);
    vi.mocked(createWorkspaceStudy).mockResolvedValueOnce(newStudy);

    render(
      <MemoryRouter>
        <ResearchBacktestPage />
      </MemoryRouter>,
    );

    await screen.findByText(/SMA Crossover 20\/50/);
    const studySelect = screen.getAllByRole("combobox")[0];
    fireEvent.keyDown(studySelect, { key: "Enter" });
    fireEvent.click(
      await screen.findByRole("option", { name: "Prior Study" }),
    );

    fireEvent.change(screen.getByPlaceholderText("e.g. SMA Swing Research"), {
      target: { value: "New Study" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(createWorkspaceStudy).toHaveBeenCalledWith("New Study"));
    await act(async () => {
      resolveOld(strategies);
      await oldRead;
    });

    expect(screen.queryByText(/SMA Crossover 20\/50/)).not.toBeInTheDocument();
  });


  it("reopens a saved registered Backtest result", async () => {
    render(
      <MemoryRouter>
        <ResearchBacktestPage />
      </MemoryRouter>,
    );
    await screen.findByText(/SMA Crossover 20\/50/);
    fireEvent.click(screen.getByRole("button", { name: "Open Result" }));
    await waitFor(() => {
      expect(getWorkspaceBacktestResult).toHaveBeenCalledWith(
        strategies.strategies[0].trial_id,
      );
    });
    expect(await screen.findByText("Evidence")).toBeInTheDocument();
    expect(screen.getByText("Losing Trades")).toBeInTheDocument();
    expect(screen.getByText("Transaction Costs")).toBeInTheDocument();
    expect(screen.getByText("Gross Realized PnL")).toBeInTheDocument();
    expect(screen.getByText("Account PnL")).toBeInTheDocument();
    expect(screen.getByText("Mean Instrument Return")).toBeInTheDocument();
  });


  it("sends Retry with the exact displayed Trial disposition generation", async () => {
    const retryable = {
      ...strategies,
      strategies: [
        {
          ...strategies.strategies[0],
          trial_disposition: "FAILED",
          trial_disposition_event_id: "trial-event-failed-2",
          retryable: true,
        },
      ],
    };
    vi.mocked(getWorkspaceStrategies).mockResolvedValue(retryable);
  
    render(
      <MemoryRouter>
        <ResearchBacktestPage />
      </MemoryRouter>,
    );
  
    await screen.findByText(/SMA Crossover 20\/50/);
    fireEvent.click(screen.getByRole("button", { name: "Retry Backtest" }));
  
    await waitFor(() => {
      expect(retryWorkspaceBacktest).toHaveBeenCalledWith(
        retryable.strategies[0].trial_id,
        "trial-event-failed-2",
      );
    });
  });

});
