// src/runtime/replay/useReplayController.ts

import {
  useEffect,
  useRef,
  useState,
} from "react";

import type {
  BarRecord,
} from "../../types/BarRecord";

export function useReplayController() {
  const [records, setRecords] = useState<
    BarRecord[]
  >([]);

  const [cursor, setCursor] = useState(0);

  const [isPlaying, setIsPlaying] =
    useState(false);

  const [error, setError] = useState<
    string | null
  >(null);

  const timerRef = useRef<number | null>(
    null
  );

  // -----------------------------------------
  // LOAD REPLAY DATA
  // -----------------------------------------
  useEffect(() => {
    fetch("/replay/RELIANCE_15m_bars.json")
      .then((res) => {
        if (!res.ok) {
          throw new Error(
            "Failed to load replay JSON"
          );
        }

        return res.json();
      })
      .then((data: BarRecord[]) => {
        if (!Array.isArray(data)) {
          throw new Error(
            "Replay JSON is not an array"
          );
        }

        setRecords(data);
        setCursor(0);
      })
      .catch((err) => {
        console.error(err);
        setError(err.message);
      });
  }, []);

  // -----------------------------------------
  // CONTROLS
  // -----------------------------------------

  const nextBar = () =>
    setCursor((c) =>
      Math.min(c + 1, records.length - 1)
    );

  const prevBar = () =>
    setCursor((c) => Math.max(c - 1, 0));

  const play = () => {
    if (timerRef.current !== null) return;

    setIsPlaying(true);

    timerRef.current = window.setInterval(
      () => {
        setCursor((c) => {
          if (c >= records.length - 1) {
            pause();
            return c;
          }

          return c + 1;
        });
      },
      600
    );
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

  const runFullReplay = () => {
    pause();
    setCursor(records.length - 1);
  };

  return {
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
  };
}