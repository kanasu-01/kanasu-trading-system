from core.research.models.research_request import ResearchRequest
from core.research.models.research_result import ResearchResult


class ResearchSession:
    """
    Unified research workflow orchestrator.

    MVP v1 responsibilities:
    - receive research request
    - route to execution mode
    - return research result
    """

    def run(self, request: ResearchRequest) -> ResearchResult:

        if request.mode == "BACKTEST":
            return ResearchResult(
                success=True,
                message="Backtest execution placeholder.",
            )

        if request.mode == "WFA":
            return ResearchResult(
                success=True,
                message="WFA execution placeholder.",
            )

        if request.mode == "REPLAY":
            return ResearchResult(
                success=True,
                message="Replay execution placeholder.",
            )

        return ResearchResult(
            success=False,
            message=f"Unsupported research mode: {request.mode}",
        )
