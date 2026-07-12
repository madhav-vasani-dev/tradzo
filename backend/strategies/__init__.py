"""Strategy Registry — maps STRATEGY_CODE strings to their implementation class.

Adding a new strategy:
  1. Implement a class that extends BaseStrategy in this package.
  2. Import it here and add it to REGISTRY.
  3. The execution engine picks it up automatically — no other changes needed.
"""

from strategies.base_strategy import BaseStrategy  # noqa: F401 — re-exported
from strategies.nifty_straddle import NiftyStraddleStrategy

REGISTRY: dict[str, type[BaseStrategy]] = {
    NiftyStraddleStrategy.STRATEGY_CODE: NiftyStraddleStrategy,
}


def get_strategy(code: str) -> BaseStrategy:
    """Return an instance of the strategy class for the given code.

    Raises ValueError if the code is not registered.
    """
    cls = REGISTRY.get(code)
    if not cls:
        raise ValueError(
            f"Unknown strategy code: '{code}'. "
            f"Registered codes: {list(REGISTRY.keys())}"
        )
    return cls()
