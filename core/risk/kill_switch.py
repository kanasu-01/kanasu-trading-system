class KillSwitch:
    """
    Global emergency kill switch.
    """

    def __init__(self):
        self._enabled = False
        self._reason = None

    def activate(self, reason: str) -> None:
        self._enabled = True
        self._reason = reason

    def deactivate(self) -> None:
        self._enabled = False
        self._reason = None

    def is_active(self) -> bool:
        return self._enabled

    def reason(self):
        return self._reason
