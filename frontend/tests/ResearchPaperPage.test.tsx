import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  getResearchWorkspaceConfig,
  getWorkspacePaperCampaigns,
  getWorkspacePaperHistory,
  stopWorkspacePaper,
} from "@/api/researchWorkspaceApi";
import { ResearchPaperPage } from "@/pages/ResearchPaperPage";
import type { WorkspacePaperHistory } from "@/types/researchWorkspace";

vi.mock("@/api/researchWorkspaceApi", () => ({
  getResearchWorkspaceConfig: vi.fn(),
  getWorkspacePaperCampaigns: vi.fn(),
  getWorkspacePaperHistory: vi.fn(),
  startWorkspacePaper: vi.fn(),
  stopWorkspacePaper: vi.fn(),
}));

describe("ResearchPaperPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(getResearchWorkspaceConfig).mockResolvedValue({
      markets: [{ id: "NSE", name: "NSE" }],
      symbols: [{ symbol: "RELIANCE", exchange: "NSE" }],
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
      active_qualification_policy: null,
    });
    vi.mocked(getWorkspacePaperCampaigns).mockResolvedValue({
      study_id: "study-1",
      campaigns: [
        {
          campaign_id: "campaign-1",
          study_id: "study-1",
          study_revision_id: "sha256:" + "1".repeat(64),
          trial_id: "sha256:" + "2".repeat(64),
          candidate_revision_id: "sha256:" + "3".repeat(64),
          strategy_label: "SMA Crossover 20/50",
          wfa_decision_id: "wfa-1",
          created_at: "2026-11-07T00:00:00Z",
          current_authority: true,
        },
        {
          campaign_id: "campaign-2",
          study_id: "study-1",
          study_revision_id: "sha256:" + "4".repeat(64),
          trial_id: "sha256:" + "5".repeat(64),
          candidate_revision_id: "sha256:" + "6".repeat(64),
          strategy_label: "SMA Crossover 25/55",
          wfa_decision_id: "wfa-2",
          created_at: "2026-11-07T00:01:00Z",
          current_authority: false,
        },
      ],
    });
    vi.mocked(getWorkspacePaperHistory).mockResolvedValue({
      campaign: {
        campaign_id: "campaign-1",
        study_id: "study-1",
        study_revision_id: "sha256:" + "1".repeat(64),
        trial_id: "sha256:" + "2".repeat(64),
        candidate_revision_id: "sha256:" + "3".repeat(64),
        strategy_label: "SMA Crossover 20/50",
        wfa_decision_id: "wfa-1",
        created_at: "2026-11-07T00:00:00Z",
        current_authority: true,
      },
      sessions: [],
      runtime: { active: false, snapshot: null },
      campaign_owns_runtime: false,
    });
  });

  it("opens in Qualified Research mode with current campaign authority", async () => {
    render(
      <MemoryRouter>
        <ResearchPaperPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("SMA Crossover 20/50")).toBeInTheDocument();
    expect(screen.getByText(/WFA authority:/i)).toHaveTextContent("CURRENT");
    expect(
      screen.getByRole("button", { name: "Standalone Smoke" }),
    ).toBeInTheDocument();
  });

  it("does not let a late RUNNING poll overwrite a confirmed STOPPED response", async () => {
    const campaign = {
      campaign_id: "campaign-1",
      study_id: "study-1",
      study_revision_id: "sha256:" + "1".repeat(64),
      trial_id: "sha256:" + "2".repeat(64),
      candidate_revision_id: "sha256:" + "3".repeat(64),
      strategy_label: "SMA Crossover 20/50",
      wfa_decision_id: "wfa-1",
      created_at: "2026-11-07T00:00:00Z",
      current_authority: true,
    };
    const runningHistory: WorkspacePaperHistory = {
      campaign,
      sessions: [
        {
          session_id: "session-a",
          state: "RUNNING",
          created_at: "2026-11-07T00:00:00Z",
          started_at: "2026-11-07T00:00:01Z",
          terminal_at: null,
          failure_type: null,
          failure_message: null,
        },
      ],
      runtime: {
        active: true,
        snapshot: {
          session_id: "session-a",
          status: "RUNNING",
          strategy_name: "SMA Crossover 20/50",
          symbol: "RELIANCE",
          started_at: "2026-11-07T00:00:01Z",
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
        },
      },
      campaign_owns_runtime: true,
    };
    const stoppedHistory: WorkspacePaperHistory = {
      ...runningHistory,
      sessions: [
        {
          ...runningHistory.sessions[0],
          state: "STOPPED",
          terminal_at: "2026-11-07T00:00:02Z",
        },
      ],
      runtime: {
        active: false,
        snapshot: {
          ...runningHistory.runtime!.snapshot!,
          status: "STOPPED",
          stopped_at: "2026-11-07T00:00:02Z",
        },
      },
    };

    let pollHandler: (() => void) | null = null;
    const realSetTimeout = window.setTimeout.bind(window);
    const timeoutSpy = vi
      .spyOn(window, "setTimeout")
      .mockImplementation((handler, timeout, ...args) => {
        if (timeout === 2000) {
          pollHandler = handler as () => void;
          return 1;
        }
        return realSetTimeout(handler, timeout, ...args);
      });
    let resolvePoll!: (value: WorkspacePaperHistory) => void;
    const latePoll = new Promise<WorkspacePaperHistory>((resolve) => {
      resolvePoll = resolve;
    });

    vi.mocked(getWorkspacePaperHistory)
      .mockResolvedValueOnce(runningHistory)
      .mockReturnValueOnce(latePoll);
    vi.mocked(stopWorkspacePaper).mockResolvedValue(stoppedHistory);

    try {
      render(
        <MemoryRouter>
          <ResearchPaperPage />
        </MemoryRouter>,
      );

      const stopButton = await screen.findByRole("button", {
        name: "Stop Paper Trading",
      });
      await waitFor(() => expect(stopButton).toBeEnabled());
      await waitFor(() => expect(pollHandler).not.toBeNull());

      act(() => {
        pollHandler?.();
      });
      fireEvent.click(stopButton);

      await waitFor(() => {
        expect(stopWorkspacePaper).toHaveBeenCalledWith("campaign-1");
      });
      await waitFor(() => {
        expect(screen.getAllByText("STOPPED").length).toBeGreaterThan(0);
      });

      await act(async () => {
        resolvePoll(runningHistory);
        await latePoll;
      });

      expect(screen.queryByText("RUNNING")).not.toBeInTheDocument();
      expect(screen.getAllByText("STOPPED").length).toBeGreaterThan(0);
    } finally {
      timeoutSpy.mockRestore();
    }
  });


  it("does not schedule another same-generation poll until the current poll settles", async () => {
    const campaign = {
      campaign_id: "campaign-1",
      study_id: "study-1",
      study_revision_id: "sha256:" + "1".repeat(64),
      trial_id: "sha256:" + "2".repeat(64),
      candidate_revision_id: "sha256:" + "3".repeat(64),
      strategy_label: "SMA Crossover 20/50",
      wfa_decision_id: "wfa-1",
      created_at: "2026-11-07T00:00:00Z",
      current_authority: true,
    };
    const runningHistory: WorkspacePaperHistory = {
      campaign,
      sessions: [{
        session_id: "session-a",
        state: "RUNNING",
        created_at: "2026-11-07T00:00:00Z",
        started_at: "2026-11-07T00:00:01Z",
        terminal_at: null,
        failure_type: null,
        failure_message: null,
      }],
      runtime: {
        active: true,
        snapshot: {
          session_id: "session-a", status: "RUNNING",
          strategy_name: "SMA Crossover 20/50", symbol: "RELIANCE",
          started_at: "2026-11-07T00:00:01Z", stopped_at: null,
          initial_capital: 100000, cash: 100000, position_size: 0,
          position_value: 0, equity: 100000, realized_pnl: 0,
          unrealized_pnl: 0, total_pnl: 0, peak_equity: 100000,
          drawdown: 0, active_position: null, completed_trade_count: 0,
          last_execution_event: null, last_execution_price: null,
          last_execution_quantity: null, failure_type: null, failure_message: null,
        },
      },
      campaign_owns_runtime: true,
    };

    const timeoutHandlers: Array<() => void> = [];
    const realSetTimeout = window.setTimeout.bind(window);
    const timeoutSpy = vi.spyOn(window, "setTimeout").mockImplementation((handler, timeout, ...args) => {
      if (timeout === 2000) {
        timeoutHandlers.push(handler as () => void);
        return timeoutHandlers.length;
      }
      return realSetTimeout(handler, timeout, ...args);
    });
    let resolvePoll!: (value: WorkspacePaperHistory) => void;
    const pendingPoll = new Promise<WorkspacePaperHistory>((resolve) => {
      resolvePoll = resolve;
    });
    vi.mocked(getWorkspacePaperHistory)
      .mockResolvedValueOnce(runningHistory)
      .mockReturnValueOnce(pendingPoll);

    try {
      render(
        <MemoryRouter>
          <ResearchPaperPage />
        </MemoryRouter>,
      );
      await screen.findByRole("button", { name: "Stop Paper Trading" });
      await waitFor(() => expect(timeoutHandlers.length).toBe(1));

      act(() => {
        timeoutHandlers[0]();
      });
      await waitFor(() => expect(getWorkspacePaperHistory).toHaveBeenCalledTimes(2));
      expect(timeoutHandlers).toHaveLength(1);

      await act(async () => {
        resolvePoll(runningHistory);
        await pendingPoll;
      });
      await waitFor(() => expect(timeoutHandlers.length).toBe(2));
    } finally {
      timeoutSpy.mockRestore();
    }
  });


  it("restarts polling after a failed Stop while the runtime remains active", async () => {
    const campaign = {
      campaign_id: "campaign-1",
      study_id: "study-1",
      study_revision_id: "sha256:" + "1".repeat(64),
      trial_id: "sha256:" + "2".repeat(64),
      candidate_revision_id: "sha256:" + "3".repeat(64),
      strategy_label: "SMA Crossover 20/50",
      wfa_decision_id: "wfa-1",
      created_at: "2026-11-07T00:00:00Z",
      current_authority: true,
    };
    const runningHistory: WorkspacePaperHistory = {
      campaign,
      sessions: [
        {
          session_id: "session-a",
          state: "RUNNING",
          created_at: "2026-11-07T00:00:00Z",
          started_at: "2026-11-07T00:00:01Z",
          terminal_at: null,
          failure_type: null,
          failure_message: null,
        },
      ],
      runtime: {
        active: true,
        snapshot: {
          session_id: "session-a",
          status: "RUNNING",
          strategy_name: "SMA Crossover 20/50",
          symbol: "RELIANCE",
          started_at: "2026-11-07T00:00:01Z",
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
        },
      },
      campaign_owns_runtime: true,
    };
    const refreshedHistory: WorkspacePaperHistory = {
      ...runningHistory,
      runtime: {
        active: true,
        snapshot: {
          ...runningHistory.runtime!.snapshot!,
          completed_trade_count: 7,
        },
      },
    };

    const timeoutHandlers: Array<() => void> = [];
    const realSetTimeout = window.setTimeout.bind(window);
    const timeoutSpy = vi
      .spyOn(window, "setTimeout")
      .mockImplementation((handler, timeout, ...args) => {
        if (timeout === 2000) {
          timeoutHandlers.push(handler as () => void);
          return timeoutHandlers.length;
        }
        return realSetTimeout(handler, timeout, ...args);
      });

    vi.mocked(getWorkspacePaperHistory)
      .mockResolvedValueOnce(runningHistory)
      .mockResolvedValueOnce(refreshedHistory);
    vi.mocked(stopWorkspacePaper).mockRejectedValueOnce(
      new Error("stop failed"),
    );

    try {
      render(
        <MemoryRouter>
          <ResearchPaperPage />
        </MemoryRouter>,
      );

      const stopButton = await screen.findByRole("button", {
        name: "Stop Paper Trading",
      });
      await waitFor(() => expect(timeoutHandlers.length).toBe(1));

      fireEvent.click(stopButton);
      expect(await screen.findByText("stop failed")).toBeInTheDocument();
      await waitFor(() => expect(timeoutHandlers.length).toBeGreaterThan(1));

      await act(async () => {
        timeoutHandlers.at(-1)?.();
      });

      await waitFor(() => {
        expect(screen.getByText("7")).toBeInTheDocument();
      });
    } finally {
      timeoutSpy.mockRestore();
    }
  });


});
