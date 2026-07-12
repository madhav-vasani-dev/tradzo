"""Abstract base class for all Tradzo strategies.

Every strategy must:
  - Declare STRATEGY_CODE, LOT_SIZE, STOP_LOSS_PCT as class attributes.
  - Implement the three abstract methods below.

The execution engine calls these methods at 12:00 PM (entry) and 15:29 PM (exit).
No strategy implementation should interact directly with Firestore or the broker
API — those concerns belong in order_service and position_service.
"""
from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    # ── Must be overridden in every concrete strategy ─────────────────────────
    STRATEGY_CODE: str = ""       # e.g. "NIFTY_STRADDLE"
    LOT_SIZE: int = 1             # Units per lot
    STOP_LOSS_PCT: float = 0.0    # % above entry price that triggers SL (for shorts)

    # ── Entry ─────────────────────────────────────────────────────────────────

    @abstractmethod
    def get_entry_legs(
        self,
        deployment: dict,
        atm_strike: int,
        expiry: str,
        lots: int,
    ) -> list[dict]:
        """Return the list of legs to sell at entry.

        Each leg is a dict with keys:
          - optionType: "CE" | "PE"
          - strike:      int
          - expiry:      "YYYY-MM-DD"
          - quantity:    int (total units, already multiplied by lots)
        """

    # ── Stop-loss ─────────────────────────────────────────────────────────────

    @abstractmethod
    def calculate_sl_price(self, entry_price: float) -> float:
        """Return the SL trigger price for a short leg filled at entry_price.

        For a SELL position, SL is triggered when the option price RISES above
        this level (i.e. a loss for the seller).

        Example (30% SL on a sell at 100): returns 130.0
        """

    # ── Exit / square-off ────────────────────────────────────────────────────

    @abstractmethod
    def get_square_off_order(self, position: dict) -> dict:
        """Return the order payload needed to close an open short position.

        `position` is the Firestore position document dict.
        The returned dict must be a valid Upstox place-order payload
        (transaction_type=BUY, order_type=MARKET, etc.).
        """
