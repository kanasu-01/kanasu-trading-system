import json
from pathlib import Path
from typing import Optional, Dict


class StateStore:
    """
    Persistent runtime state store.
    """

    def __init__(
        self,
        state_dir: str = "state",
        filename: str = "runtime_state.json",
    ):
        self.state_path = Path(state_dir)
        self.state_path.mkdir(parents=True, exist_ok=True)

        self.file = self.state_path / filename

    def save(
        self,
        open_position: Optional[Dict],
        metadata: Optional[Dict] = None,
    ) -> None:
        payload = {
            "open_position": open_position,
            "metadata": metadata or {},
        }

        with open(self.file, "w") as f:
            json.dump(payload, f, indent=2)

    def load(self) -> Dict:
        if not self.file.exists():
            return {
                "open_position": None,
                "metadata": {},
            }

        with open(self.file, "r") as f:
            return json.load(f)

    def clear(self) -> None:
        if self.file.exists():
            self.file.unlink()
