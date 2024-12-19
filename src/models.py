from dataclasses import dataclass
from typing import List, Optional
from enum import Enum

class PositionSide(Enum):
    LONG = "LONG"
    SHORT = "SHORT"

@dataclass
class TrailingConfig:
    stop: str
    trigger: str

@dataclass
class Signal:
    symbol: str
    side: PositionSide
    leverage: int
    entry: float
    targets: List[float]
    stoploss: float
    trailing_config: Optional[TrailingConfig] = None

    def get_bitmart_side(self) -> int:
        """Convert position side to BitMart API format"""
        if self.side == PositionSide.LONG:
            return 1  # buy_open_long
        return 4  # sell_open_short 