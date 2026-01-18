from enum import Enum
from typing import Optional

from core.entities.candle_series import CandleSeries
from core.models.accumulation_score import AccumulationScorer
from core.models.distribution_score import DistributionScorer
from core.models.phase_confidence import PhaseConfidence
from core.metrics.volatility_metrics import VolatilityMetrics
from core.strategies.base_strategy import BaseStrategy


class PivotBossState(Enum):
    NO_TRADE = "NO_TRADE"
    ACCUMULATION_CONFIRMED = "ACCUMULATION_CONFIRMED"
    REJECTION_DETECTED = "REJECTION_DETECTED"
    ABSORPTION_ACTIVE = "ABSORPTION_ACTIVE"
    MARKUP_CONFIRMED = "MARKUP_CONFIRMED"
    POSITION_ACTIVE = "POSITION_ACTIVE"


class PivotBossSwingStrategy(BaseStrategy):
    """
    PivotBoss Accumulation → Markup Swing Strategy
    STEP 6.5: Confidence score gating for entries.
    """

    def __init__(self, params=None):
        super().__init__(name="PivotBossSwing", params=params)

        # Intelligence
        self.acc_scorer = AccumulationScorer()
        self.dist_scorer = DistributionScorer()

        # ---------------- PARAMETERS ----------------

        self.min_acc_score = self.get_param("min_acc_score", 70)

        # Rejection
        self.rejection_close_pct = self.get_param("rejection_close_pct", 0.25)
        self.rejection_volume_multiplier = self.get_param(
            "rejection_volume_multiplier", 1.2
        )

        # Absorption
        self.absorption_lookback = self.get_param("absorption_lookback", 3)

        # Markup
        self.markup_lookback = self.get_param("markup_lookback", 20)
        self.markup_volume_multiplier = self.get_param(
            "markup_volume_multiplier", 1.3
        )

        # Exit
        self.distribution_exit_threshold = self.get_param(
            "distribution_exit_threshold", 10
        )

        # Scale-in
        self.max_scale_entries = self.get_param("max_scale_entries", 3)

        # Time-based exit
        self.max_stagnation_candles = self.get_param(
            "max_stagnation_candles", 10
        )
        self.min_progress_pct = self.get_param(
            "min_progress_pct", 1.0
        )

        # Confidence filter (NEW)
        self.min_confidence_to_trade = self.get_param(
            "min_confidence_to_trade", 60
        )

        # ---------------- STATE ----------------

        self.state = PivotBossState.NO_TRADE
        self.decision_reason: Optional[str] = None

        self.rejection_midpoint: Optional[float] = None
        self.accumulation_high: Optional[float] = None

        self.entry_count = 0
        self.entry_index: Optional[int] = None
        self.best_price_since_entry: Optional[float] = None

        self.confidence_score: Optional[float] = None

    def warmup_bars(self) -> int:
        return super().warmup_bars() + 30  # for volatility and structure calculations
    
    
    def reset(self) -> None:
        self.state = PivotBossState.NO_TRADE
        self.rejection_midpoint = None
        self.accumulation_high = None
        self.entry_count = 0
        self.entry_index = None
        self.best_price_since_entry = None
        self.confidence_score = None
        self.decision_reason = "Reset after exit"

    # ---------- CONFIDENCE ----------

    def _compute_confidence(self, series: CandleSeries) -> float:
        """
        Returns a confidence score between 0 and 100.
        """
        score = 0.0

        acc_score = self.acc_scorer.score(series)
        if acc_score >= self.min_acc_score:
            score += 30

        if self.state == PivotBossState.ABSORPTION_ACTIVE:
            score += 20

        if self.state == PivotBossState.MARKUP_CONFIRMED:
            score += 25

        volatility_ok = VolatilityMetrics.is_volatility_contracting(
            series, short_window=3, long_window=10
        )
        if volatility_ok:
            score += 15

        # Pullback holding value
        candle = series[-1]
        if (
            self.rejection_midpoint is not None
            and candle.close >= self.rejection_midpoint
        ):
            score += 10

        return min(score, 100.0)

    # ---------- REJECTION ----------

    def _is_rejection_day(self, series: CandleSeries) -> bool:
        if len(series) < 2:
            return False

        candle = series[-1]
        prev = series[-2]

        lower_low = candle.low < prev.low
        candle_range = candle.high - candle.low
        if candle_range == 0:
            return False

        close_near_high = (
            (candle.high - candle.close) / candle_range
        ) <= self.rejection_close_pct

        volume_expansion = (
            candle.volume >= prev.volume * self.rejection_volume_multiplier
        )

        return lower_low and close_near_high and volume_expansion

    # ---------- ABSORPTION ----------

    def _is_absorption_active(self, series: CandleSeries) -> bool:
        if self.rejection_midpoint is None:
            return False

        if len(series) < self.absorption_lookback:
            return False

        recent = series[-self.absorption_lookback:]

        defended = all(
            candle.close >= self.rejection_midpoint
            for candle in recent
        )

        volatility_ok = VolatilityMetrics.is_volatility_contracting(
            series, short_window=3, long_window=10
        )

        return defended and volatility_ok

    # ---------- MARKUP ----------

    def _is_markup_confirmed(self, series: CandleSeries) -> bool:
        if len(series) < self.markup_lookback:
            return False

        recent = series[-self.markup_lookback:]
        candle = series[-1]

        range_high = max(c.high for c in recent)

        breakout = candle.close > range_high

        avg_volume = sum(c.volume for c in recent[:-1]) / (len(recent) - 1)
        volume_expansion = (
            candle.volume >= avg_volume * self.markup_volume_multiplier
        )

        return breakout and volume_expansion

    # ---------- ENTRY ----------

    def _is_valid_pullback_entry(self, series: CandleSeries) -> bool:
        if self.rejection_midpoint is None:
            return False

        candle = series[-1]

        return (
            candle.low <= self.rejection_midpoint
            and candle.close >= self.rejection_midpoint
        )

    # ---------- EXIT ----------

    def _time_exit_triggered(self, series: CandleSeries) -> bool:
        if self.entry_index is None:
            return False

        current_index = len(series) - 1
        candles_elapsed = current_index - self.entry_index

        candle = series[-1]
        if self.best_price_since_entry is None:
            self.best_price_since_entry = candle.high
        else:
            self.best_price_since_entry = max(
            self.best_price_since_entry,
            candle.high
        )

        progress_pct = (
            (self.best_price_since_entry - series[self.entry_index].close)
            / series[self.entry_index].close
        ) * 100

        if (
            candles_elapsed >= self.max_stagnation_candles
            and progress_pct < self.min_progress_pct
        ):
            self.decision_reason = (
                f"Exit: No progress after {candles_elapsed} candles"
            )
            return True

        return False

    def _should_exit(self, series: CandleSeries) -> bool:
        candle = series[-1]

        if candle.close < self.rejection_midpoint:
            self.decision_reason = "Exit: Structure failed"
            return True

        acc_score = self.acc_scorer.score(series)
        dist_score = self.dist_scorer.score(series)

        if dist_score > acc_score + self.distribution_exit_threshold:
            self.decision_reason = "Exit: Distribution dominance"
            return True

        if self._time_exit_triggered(series):
            return True

        return False

    # ---------- MAIN LOOP ----------

    def on_new_candle(self, series: CandleSeries) -> Optional[str]:
        
        # -----------------------------------------
        # WARM-UP PHASE (DO NOT REMOVE)
        # -----------------------------------------
        self._series = series  # for debug state
        MIN_WARMUP_BARS = 30  # safe minimum for volatility + structure

        if len(series) < MIN_WARMUP_BARS:
            return None


        acc_score = self.acc_scorer.score(series)
        dist_score = self.dist_scorer.score(series)
        phase = PhaseConfidence.determine_phase(acc_score, dist_score)
        
        vol_contract = VolatilityMetrics.is_volatility_contracting(
            series, short_window=3, long_window=10
        )

        absorption = self._is_absorption_active(series)
        markup = self._is_markup_confirmed(series)

        print(
            f"{series[-1].timestamp} | "
            f"ACC={acc_score:.2f} | "
            f"VOL_CONTRACT={vol_contract} | "
            f"ABSORB={absorption} | "
            f"MARKUP={markup} | "
            f"STATE={self.state.name}"
        )



        if self.state == PivotBossState.NO_TRADE:
            if phase == "ACCUMULATION" and acc_score >= self.min_acc_score:
                self.state = PivotBossState.ACCUMULATION_CONFIRMED
                self.accumulation_high = max(c.high for c in series)
                self.decision_reason = "Accumulation confirmed"

        elif self.state == PivotBossState.ACCUMULATION_CONFIRMED:
            if self._is_rejection_day(series):
                candle = series[-1]
                self.rejection_midpoint = (candle.high + candle.low) / 2
                self.state = PivotBossState.REJECTION_DETECTED
                self.decision_reason = "Rejection day detected"

        elif self.state == PivotBossState.REJECTION_DETECTED:
            if self._is_absorption_active(series):
                self.state = PivotBossState.ABSORPTION_ACTIVE
                self.decision_reason = "Absorption confirmed"

        elif self.state == PivotBossState.ABSORPTION_ACTIVE:
            if self._is_markup_confirmed(series):
                self.state = PivotBossState.MARKUP_CONFIRMED
                self.entry_count = 0
                self.decision_reason = "Markup confirmed"

        elif self.state in (
            PivotBossState.MARKUP_CONFIRMED,
            PivotBossState.POSITION_ACTIVE,
        ):
            self.confidence_score = self._compute_confidence(series)

            if (
                self.entry_count < self.max_scale_entries
                and self.confidence_score >= self.min_confidence_to_trade
                and self._is_valid_pullback_entry(series)
            ):
                self.entry_count += 1
                self.state = PivotBossState.POSITION_ACTIVE
                self.entry_index = len(series) - 1
                self.best_price_since_entry = series[-1].high
                self.decision_reason = (
                    f"BUY: Confidence {self.confidence_score:.1f}"
                )
                return "BUY"

            if self.state == PivotBossState.POSITION_ACTIVE:
                if self._should_exit(series):
                    self.reset()
                    return "SELL"

        return None
    
    def get_debug_state(self) -> dict:
        
        if not hasattr(self, "_series"):
            return {}
        
        if len (self._series) < self.warmup_bars():
            return {
                "acc_score": None,
                "dist_score": None,
                "confidence": None,
                "absorption_active": None,
                "markup_confirmed": None,
                "volatility_contracting": None,
            }
        return {
            "state": self.state.value,
            "acc_score": self.acc_scorer.score(self._series) if hasattr(self, "_series") else None,
            "dist_score": self.dist_scorer.score(self._series) if hasattr(self, "_series") else None,
            "confidence": self.confidence_score,
            "absorption_active": self.state == PivotBossState.ABSORPTION_ACTIVE,
            "markup_confirmed": self.state == PivotBossState.MARKUP_CONFIRMED,
            "volatility_contracting": VolatilityMetrics.is_volatility_contracting(
                self._series, short_window=3, long_window=10
            ) if hasattr(self, "_series") else None,
        }