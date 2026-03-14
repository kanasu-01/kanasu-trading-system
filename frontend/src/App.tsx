import { useEffect, useRef, useState } from "react";
import type { BarRecord } from "./types/BarRecord";
import { DecisionBox } from "./components/DecisionBox";
import { CandleChart } from "./components/CandleChart";

export default function App() {
  const [records, setRecords] = useState<BarRecord[]>([]);
  const [cursor, setCursor] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const timerRef = useRef<number | null>(null);

  // --------------------------------------------------
  // LOAD BAR RECORDS
  // --------------------------------------------------
  useEffect(() => {
    fetch("/replay/RELIANCE_15m_bars.json")
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load replay JSON");
        return res.json();
      })
      .then((data: BarRecord[]) => {
        if (!Array.isArray(data)) {
          throw new Error("Replay JSON is not an array");
        }
        setRecords(data);
        setCursor(0);
      })
      .catch((err) => {
        console.error(err);
        setError(err.message);
      });
  }, []);

  const currentBar = records[cursor];

  // --------------------------------------------------
  // REPLAY CONTROLS
  // --------------------------------------------------
  const nextBar = () =>
    setCursor((c) => Math.min(c + 1, records.length - 1));

  const prevBar = () =>
    setCursor((c) => Math.max(c - 1, 0));

  const play = () => {
    if (timerRef.current !== null) return;

    setIsPlaying(true);
    timerRef.current = window.setInterval(() => {
      setCursor((c) => {
        if (c >= records.length - 1) {
          pause();
          return c;
        }
        return c + 1;
      });
    }, 600);
  };

  const pause = () => {
    setIsPlaying(false);
    if (timerRef.current !== null) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  const reset = () => {
    pause();
    setCursor(0);
  };

  // --------------------------------------------------
  // UI
  // --------------------------------------------------
  return (
    <div
      style={{
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        padding: 12,
        boxSizing: "border-box",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 6,
        }}
      >
        <strong>Kanasu Trading System</strong>
        <span style={{ fontSize: 12, opacity: 0.7 }}>
          Replay UI – Phase 2
        </span>
      </div>

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
        <button onClick={reset}>↺</button>
      </div>

      {error && (
        <div style={{ color: "red", marginBottom: 8 }}>
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
          <div style={{ flex: 1, minHeight: 0 }}>
            <CandleChart records={records} cursor={cursor} />
          </div>

          {/* DECISION PANEL — FULLY STRATEGY AGNOSTIC */}
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
                : currentBar.decision_snapshot ?? {}
            ).map(([key, value]) => (
              <DecisionBox
                key={key}
                label={key}
                value={value}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
