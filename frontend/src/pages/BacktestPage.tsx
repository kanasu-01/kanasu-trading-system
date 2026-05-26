// frontend/src/pages/BacktestPage.tsx

import { CandleChart } from "../components/CandleChart";
import { DecisionBox } from "../components/DecisionBox";
import { PerformancePanel } from "../PerformancePanel";

import { AppLayout } from "../app/AppLayout";

import { useReplayController } from "../runtime/replay/useReplayController";

export function BacktestPage() {
  const {
    records,
    cursor,
    isPlaying,
    error,

    nextBar,
    prevBar,
    play,
    pause,
    reset,
    runFullReplay,
  } = useReplayController();

  const currentBar = records[cursor];

  return (
    <AppLayout>
      <div
        style={{
          height: "100%",
          display: "flex",
          flexDirection: "column",
          padding: 12,
          boxSizing: "border-box",
        }}
      >
        {/* Controls */}
        <div style={{ marginBottom: 8 }}>
          <button onClick={prevBar}>◀</button>{" "}
          <button onClick={nextBar}>▶</button>{" "}
          <button onClick={play} disabled={isPlaying}>
            ⏵
          </button>{" "}
          <button onClick={pause} disabled={!isPlaying}>
            ⏸
          </button>{" "}
          <button onClick={reset}>↺</button>{" "}
          <button onClick={runFullReplay}>⚡ Run Full</button>
        </div>

        {error && (
          <div
            style={{
              color: "red",
              marginBottom: 8,
            }}
          >
            Error: {error}
          </div>
        )}

        {!currentBar ? (
          <div>Loading replay data…</div>
        ) : (
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              minHeight: 0,
            }}
          >
            {/* CHART */}
            <div
              style={{
                flex: 1,
                minHeight: 0,
              }}
            >
              <CandleChart records={records} cursor={cursor} />
            </div>

            {/* PERFORMANCE PANEL */}
            <PerformancePanel records={records} cursor={cursor} />

            {/* DECISION PANEL */}
            <div
              style={{
                height: 140,
                paddingTop: 8,
                borderTop: "1px solid #333",
                display: "flex",
                flexWrap: "wrap",
                gap: 8,
                overflowY: "auto",
              }}
            >
              {Object.entries(
                typeof currentBar.decision_snapshot === "string"
                  ? JSON.parse(currentBar.decision_snapshot)
                  : (currentBar.decision_snapshot ?? {}),
              ).map(([key, value]) => (
                <DecisionBox key={key} label={key} value={value} />
              ))}
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
