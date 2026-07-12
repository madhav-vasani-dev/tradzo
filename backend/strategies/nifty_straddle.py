"""Nifty Straddle Strategy.

Rules
-----
Entry   : 12:00 PM — sell ATM Nifty CE + PE (current Tuesday expiry).
Stop-loss: 30 % above entry price per leg, placed as BUY SL-M at entry time.
Exit    : 15:29 PM — cancel open SL orders, place BUY MARKET for all open legs.

Lot size : 65 units (current NSE lot size for Nifty 50 options).
Minimum  : 1 lot = ₹3,00,000 margin.
Multiplier: user selects at deploy time (1x, 2x, 3x …).
"""

from strategies.base_strategy import BaseStrategy


class NiftyStraddleStrategy(BaseStrategy):
    STRATEGY_CODE = "NIFTY_STRADDLE"
    LOT_SIZE = 65        # NSE Nifty 50 options lot size
    STOP_LOSS_PCT = 30.0  # 30 % above entry price triggers SL for short leg

    # ── Entry ─────────────────────────────────────────────────────────────────

    def get_entry_legs(
        self,
        deployment: dict,
        atm_strike: int,
        expiry: str,
        lots: int,
    ) -> list[dict]:
        """Return CE + PE legs to sell at entry.

        Both legs share the same ATM strike and expiry.
        Quantity = lots × LOT_SIZE.
        """
        qty = lots * self.LOT_SIZE
        return [
            {
                "optionType": "CE",
                "strike": atm_strike,
                "expiry": expiry,
                "quantity": qty,
            },
            {
                "optionType": "PE",
                "strike": atm_strike,
                "expiry": expiry,
                "quantity": qty,
            },
        ]

    # ── Stop-loss ─────────────────────────────────────────────────────────────

    def calculate_sl_price(self, entry_price: float) -> float:
        """SL = entry × 1.30 (30 % adverse move for short options).

        Rounded to one decimal for Upstox trigger price.
        """
        return round(entry_price * (1 + self.STOP_LOSS_PCT / 100), 1)

    # ── Exit / square-off ────────────────────────────────────────────────────

    def get_square_off_order(self, position: dict) -> dict:
        """BUY MARKET to close the short leg."""
        return {
            "instrument_token": position["instrumentKey"],
            "quantity": position["quantity"],
            "order_type": "MARKET",
            "transaction_type": "BUY",
            "product": "I",          # Intraday (MIS)
            "validity": "DAY",
            "disclosed_quantity": 0,
            "trigger_price": 0,
            "is_amo": False,
            "tag": f"SQ_{position['id'][:8].upper()}",
        }
