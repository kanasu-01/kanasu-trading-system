from typing import Dict, Optional

from core.entities.position import Position


class PositionBook:
    """
    Maintains active portfolio positions.

    Initial MVP:
    - single symbol support
    - future-ready for multi-symbol evolution
    """

    def __init__(self):

        self.positions: Dict[str, Position] = {}

    # -----------------------------------------
    # Add position
    # -----------------------------------------

    def add_position(
        self,
        symbol: str,
        position: Position,
    ) -> None:

        self.positions[symbol] = position

    # -----------------------------------------
    # Remove position
    # -----------------------------------------

    def remove_position(
        self,
        symbol: str,
    ) -> None:

        if symbol in self.positions:
            del self.positions[symbol]

    # -----------------------------------------
    # Get position
    # -----------------------------------------

    def get_position(
        self,
        symbol: str,
    ) -> Optional[Position]:

        return self.positions.get(symbol)

    # -----------------------------------------
    # Active position count
    # -----------------------------------------

    def active_count(self) -> int:

        return len(self.positions)
