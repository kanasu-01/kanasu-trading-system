import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  getResearchWorkspaceConfig,
  getWorkspaceWfa,
  runWorkspaceWfa,
  sendWorkspaceStrategiesToPaper,
} from "@/api/researchWorkspaceApi";
import { WfaPage } from "@/pages/WfaPage";
import type { WorkspaceWfaResponse } from "@/types/researchWorkspace";


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
  getResearchWorkspaceConfig: vi.fn(),
  getWorkspaceWfa: vi.fn(),
  runWorkspaceWfa: vi.fn(),
  sendWorkspaceStrategiesToPaper: vi.fn(),
}));

const config = {
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
  active_qualification_policy: {
    policy_id: "policy-1",
    version: 1,
    threshold_pct: "50",
  },
};

const wfa = {
  study_id: "study-1",
  strategies: [
    {
      trial_id: "sha256:" + "1".repeat(64),
      candidate_revision_id: "sha256:" + "2".repeat(64),
      strategy_label: "SMA Crossover 20/50",
      evidence_validity: "VALID",
      outcome: "ELIGIBLE",
      verdict: "PASS" as const,
      decision_id: "wfa-1",
      reason: "existing WFA PASS",
      metrics: {
        consistency_ratio: 0.75,
        avg_account_return_pct: 2.1,
        worst_equity_drawdown_pct: 12,
        stitched_total_return_pct: 8,
        stitched_max_drawdown_pct: 14,
        account_return_stability_score: 0.35,
      },
    },
  ],
};

describe("WfaPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    installRadixSelectDomStubs();
    vi.mocked(getResearchWorkspaceConfig).mockResolvedValue(config);
    vi.mocked(getWorkspaceWfa).mockResolvedValue(wfa);
    vi.mocked(runWorkspaceWfa).mockResolvedValue(wfa);
    vi.mocked(sendWorkspaceStrategiesToPaper).mockResolvedValue({
      study_id: "study-1",
      campaigns: [
        {
          candidate_revision_id: wfa.strategies[0].candidate_revision_id,
          strategy_label: "SMA Crossover 20/50",
          outcome: "READY",
          campaign_id: "paper-campaign-1",
          reused: false,
          reason: "Current campaign created",
        },
      ],
    });
  });

  it("shows authoritative WFA metrics and fixed Paper criteria", async () => {
    render(
      <MemoryRouter>
        <WfaPage />
      </MemoryRouter>,
    );

    expect((await screen.findAllByText("SMA Crossover 20/50")).length).toBeGreaterThan(0);
    expect(screen.getByText("75%")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "Send Strategies to Paper" }),
    );

    expect(screen.getByText(/Consistency ≥ 60%/)).toBeInTheDocument();
    expect(
      screen.getByText(/Account-return stability ≥ 0.20/),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "Confirm Send to Paper" }),
    );

    await waitFor(() => {
      expect(sendWorkspaceStrategiesToPaper).toHaveBeenCalledWith("study-1");
    });
  });

  it("preserves operational error as ERROR rather than WFA FAIL", async () => {
    vi.mocked(getWorkspaceWfa).mockResolvedValueOnce({
      study_id: "study-1",
      strategies: [
        {
          trial_id: "sha256:" + "3".repeat(64),
          candidate_revision_id: "sha256:" + "4".repeat(64),
          strategy_label: "SMA Crossover 25/55",
          evidence_validity: "UNKNOWN",
          outcome: "OPERATIONAL_ERROR",
          verdict: null,
          decision_id: null,
          reason: "provider unavailable",
          metrics: null,
        },
      ],
    });

    render(
      <MemoryRouter>
        <WfaPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("ERROR")).toBeInTheDocument();
    expect(screen.queryByText("FAIL")).not.toBeInTheDocument();
  });
  it("shows historically eligible strategies as pending before WFA", async () => {
    vi.mocked(getWorkspaceWfa).mockResolvedValueOnce({
      study_id: "study-1",
      strategies: [
        {
          trial_id: "sha256:" + "5".repeat(64),
          candidate_revision_id: "sha256:" + "6".repeat(64),
          strategy_label: "SMA Crossover 30/60",
          evidence_validity: "NOT_EVALUATED",
          outcome: "PENDING",
          verdict: null,
          decision_id: null,
          reason: "Historically eligible; WFA has not yet been evaluated",
          metrics: null,
        },
      ],
    });

    render(
      <MemoryRouter>
        <WfaPage />
      </MemoryRouter>,
    );

    expect((await screen.findAllByText("SMA Crossover 30/60")).length).toBeGreaterThan(0);
    expect(screen.getByText("PENDING")).toBeInTheDocument();
  });


  it("does not let an older WFA read overwrite a completed WFA action", async () => {
    const secondConfig = {
      ...config,
      studies: [
        ...config.studies,
        {
          study_id: "study-2",
          display_title: "SMA Research Two",
          created_at: "2026-11-07T00:10:00Z",
          archived: false,
        },
      ],
    };
    const pendingStudyTwo: WorkspaceWfaResponse = {
      study_id: "study-2",
      strategies: [
        {
          trial_id: "sha256:" + "7".repeat(64),
          candidate_revision_id: "sha256:" + "8".repeat(64),
          strategy_label: "SMA Crossover 30/60",
          evidence_validity: "NOT_EVALUATED",
          outcome: "PENDING",
          verdict: null,
          decision_id: null,
          reason: "Historically eligible; WFA has not yet been evaluated",
          metrics: null,
        },
      ],
    };
    const completedStudyTwo: WorkspaceWfaResponse = {
      study_id: "study-2",
      strategies: [
        {
          ...wfa.strategies[0],
          trial_id: "sha256:" + "7".repeat(64),
          candidate_revision_id: "sha256:" + "8".repeat(64),
          strategy_label: "SMA Crossover 30/60",
          decision_id: "wfa-2",
        },
      ],
    };
    let resolveOldRead!: (value: typeof pendingStudyTwo) => void;
    const oldRead = new Promise<typeof pendingStudyTwo>((resolve) => {
      resolveOldRead = resolve;
    });

    vi.mocked(getResearchWorkspaceConfig).mockResolvedValueOnce(secondConfig);
    vi.mocked(getWorkspaceWfa)
      .mockResolvedValueOnce(wfa)
      .mockReturnValueOnce(oldRead);
    vi.mocked(runWorkspaceWfa).mockResolvedValueOnce(completedStudyTwo);

    render(
      <MemoryRouter>
        <WfaPage />
      </MemoryRouter>,
    );

    await screen.findByText("75%");
    const studySelect = screen.getByRole("combobox");
    fireEvent.keyDown(studySelect, { key: "Enter" });
    fireEvent.click(
      await screen.findByRole("option", { name: "SMA Research Two" }),
    );
    await waitFor(() => {
      expect(studySelect).toHaveTextContent("SMA Research Two");
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Start WFA" }),
    );
    await waitFor(() => {
      expect(runWorkspaceWfa).toHaveBeenCalledWith("study-2");
    });
    await waitFor(() => {
      expect(screen.getByText("PASS")).toBeInTheDocument();
    });

    await act(async () => {
      resolveOldRead(pendingStudyTwo);
      await oldRead;
    });

    expect(screen.getByText("PASS")).toBeInTheDocument();
    expect(screen.queryByText("PENDING")).not.toBeInTheDocument();
  });

});
