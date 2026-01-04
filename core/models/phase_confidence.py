from typing import Literal


class PhaseConfidence:
    """
    Determines the dominant Wyckoff phase
    based on accumulation and distribution scores.
    """

    @staticmethod
    def determine_phase(
        accumulation_score: float,
        distribution_score: float,
        threshold: float = 10.0
    ) -> Literal["ACCUMULATION", "DISTRIBUTION", "NEUTRAL"]:

        difference = accumulation_score - distribution_score

        if difference > threshold:
            return "ACCUMULATION"

        if difference < -threshold:
            return "DISTRIBUTION"

        return "NEUTRAL"
