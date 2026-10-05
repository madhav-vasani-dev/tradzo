"""Crude Oil Mini (MCX CRUDEOILM) Straddle.

Rules
-----
Entry    : 15:30:00 IST (Mon–Fri) — sell the ATM CRUDEOILM Call + Put. ATM is the strike nearest
           the 15:30 LTP of the CRUDEOILM futures contract of the same month as the options.
Contract : nearest monthly option expiry at least `crude_min_days_to_expiry` days away
           (default 1 → on the options' expiry day the strategy trades next month).
Stop-loss: 20 % above each leg's actual fill price, placed at the broker as a BUY stop-LIMIT
           (MCX options take no stop-market orders) right after the entry fills.
Exit     : 23:24:00 IST — cancel the open stop-losses and buy back whatever is still open.

Contract : 1 lot = 10 barrels (MCX spec). Prices are per barrel, so P&L = Δprice × barrels.
Capital  : ~₹60,000 margin per lot (short straddle, Oct 2026).
Multiplier: user selects lots at deploy time (1x, 2x, …).
Brokers  : Kotak Neo, Upstox, Jainam (XTS) — and paper.

Quantity conventions differ per broker, so legs are expressed in LOTS here and converted by
the execution engine: Upstox takes commodity quantity in lots, Kotak/Jainam in multiples of
the market lot their own instrument data reports.
"""
import math

from strategies.base_strategy import BaseStrategy


class CrudeOilMiniStraddleStrategy(BaseStrategy):
    STRATEGY_CODE = "CRUDEOILM_STRADDLE"
    LOT_SIZE = 1                 # legs are sized in lots; the engine converts per broker
    UNITS_PER_LOT = 10           # barrels per CRUDEOILM lot
    STOP_LOSS_PCT = 20.0         # 20 % above entry triggers SL for each short leg
    EXCHANGE = "MCX"
    UNDERLYING = "CRUDEOILM"
    PRICE_TICK = 0.10            # stop/limit prices kept on a 10-paise grid (valid for 0.05 & 0.10 ticks)
    SUPPORTED_BROKERS = ("kotak", "upstox", "jainam")

    def get_entry_legs(self, deployment: dict, atm_strike: int, expiry: str, lots: int) -> list[dict]:
        return [
            {"optionType": "CE", "strike": atm_strike, "expiry": expiry, "quantity": lots * self.LOT_SIZE},
            {"optionType": "PE", "strike": atm_strike, "expiry": expiry, "quantity": lots * self.LOT_SIZE},
        ]

    def calculate_sl_price(self, entry_price: float) -> float:
        """SL trigger = entry × 1.20, rounded UP to the price grid.

        e.g. sold at 152.35 → 182.82 → 182.90.
        """
        raw = entry_price * (1 + self.STOP_LOSS_PCT / 100)
        return round(math.ceil(round(raw / self.PRICE_TICK, 6)) * self.PRICE_TICK, 2)

    def get_square_off_order(self, position: dict) -> dict:
        """Square-off is a protected BUY limit placed by order_service (MCX takes no market
        orders); this describes it for completeness."""
        return {
            "instrument_key": position["instrumentKey"],
            "quantity": position["quantity"],
            "transaction_type": "BUY",
            "order_type": "LIMIT",
            "validity": "DAY",
            "exchange": self.EXCHANGE,
            "tag": f"SQ_{position['id'][:8].upper()}",
        }
