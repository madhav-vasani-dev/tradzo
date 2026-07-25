"""BTC Option Selling Strategy.

Rules
-----
Instrument: BTCUSD options on Delta Exchange.
Entry     : 17:01 IST — sell ATM BTC Call + Put (today's expiry).
Stop-loss : 100% above entry price per leg (SL-M placed at entry time).
Exit      : 17:29 IST — cancel open SL orders, place BUY MARKET for all open legs.
Trail SL  : 10 pts trail, lock profit after 7 pts (monitored by sync loop).

Contract  : 1 lot = 1 Delta Exchange BTC option contract (0.001 BTC per contract).
Multiplier: user selects at deploy time (1x = 1 lot, 2x = 2 lots, …).
Currency  : Delta settles in USD. PnL is stored in both USD and INR (~85 conversion).
"""

from strategies.base_strategy import BaseStrategy


class BtcOptionSellingStrategy(BaseStrategy):
    STRATEGY_CODE = "BTC_OPTION_SELLING"
    LOT_SIZE = 1             # 1 Delta contract per lot (0.001 BTC notional)
    STOP_LOSS_PCT = 100.0    # 100% above entry price triggers SL for short leg
    TRAIL_STEP_POINTS = 10.0 # For every 10 USD points favorable move (premium drop)
    TRAIL_MOVE_POINTS = 7.0  # Reduce stop-loss by 7 USD points
    TARGET_PRICE_USD = 0.50  # Exit leg when option premium decays to $0.50 USD

    # ── Entry ─────────────────────────────────────────────────────────────────

    def get_entry_legs(
        self,
        deployment: dict,
        atm_strike: int,
        expiry: str,
        lots: int,
    ) -> list[dict]:
        """Return ATM BTC Call + Put legs to sell at entry.

        Both legs share the same ATM strike and today's expiry.
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
        """Initial SL = entry × 2.0 (100% adverse move for short options).

        For a BTC option sold at 100 USD, initial SL is placed at 200 USD.
        Rounded to 4 decimal places.
        """
        return round(entry_price * (1 + self.STOP_LOSS_PCT / 100), 4)

    def calculate_trailed_sl(
        self,
        entry_price: float,
        current_sl: float,
        current_ltp: float,
    ) -> float | None:
        """Calculate updated trailing stop-loss price based on Algotest step rules.

        Algotest Rules (Points: 10, 7):
        - Every time option premium drops by 10 points (favorable move), reduce SL by 7 points.
        - Example:
            Sold @ 100 USD -> Initial SL = 200 USD
            LTP drops to 90 (10 pts favorable) -> New SL = 200 - 7 = 193 USD
            LTP drops to 80 (20 pts favorable) -> New SL = 200 - (2 * 7) = 186 USD
            LTP drops to 70 (30 pts favorable) -> New SL = 200 - (3 * 7) = 179 USD

        Returns new lower SL price if SL should trail down, or None if unchanged.
        """
        if current_ltp <= 0 or current_ltp >= entry_price:
            return None

        initial_sl = self.calculate_sl_price(entry_price)
        favorable_move = entry_price - current_ltp

        if favorable_move < self.TRAIL_STEP_POINTS:
            return None

        # Number of 10-point steps achieved in our favor
        num_steps = int(favorable_move / self.TRAIL_STEP_POINTS)
        target_sl = initial_sl - (num_steps * self.TRAIL_MOVE_POINTS)
        target_sl = round(target_sl, 4)

        # Only trail SL DOWNWARDS (tightening the stop)
        if target_sl < current_sl:
            return target_sl

        return None

    # ── Exit / square-off ────────────────────────────────────────────────────

    def get_square_off_order(self, position: dict) -> dict:
        """Return a BUY MARKET order dict to close a short BTC option leg.

        The returned dict is forwarded to delta_service.place_order().
        Delta uses product_id (stored as instrumentKey) and size (quantity).
        """
        return {
            "product_id": int(position["instrumentKey"]),
            "size": position["quantity"],
            "side": "buy",
            "order_type": "market_order",
            "time_in_force": "ioc",                # Immediate Or Cancel for market
            "client_order_id": f"SQ_{position['id'][:8].upper()}",
        }
