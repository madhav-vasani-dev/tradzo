"""Pydantic models for the seasonality analysis module."""
from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


ViewMode = Literal["daily", "weekly", "monthly"]


# ── Request bodies ─────────────────────────────────────────────────────────────

class AddStockRequest(BaseModel):
    symbol: str = Field(..., description="Ticker symbol, e.g. NIFTY50")
    display_name: Optional[str] = None
    data_url: Optional[str] = Field(None, description="Public Google Drive or HTTP CSV link")


class RunAnalysisRequest(BaseModel):
    view_modes: list[ViewMode] = Field(default=["monthly"])
    year_ranges: list[Any] = Field(
        default=[5, 10, "max"],
        description="List of year integers or the string 'max'",
    )


class UpcomingTradesRequest(BaseModel):
    probability_threshold: float = Field(default=60.0, ge=50.0, le=100.0)
    lookahead_days: int = Field(default=30, ge=1, le=365)
    symbols: Optional[list[str]] = None
    view_mode: Optional[ViewMode] = None
    years: Optional[Any] = None
    # Return basis: "open" = (close-open)/open, "prev_close" = (close-prevClose)/prevClose
    return_basis: Literal["open", "prev_close"] = "open"
    # Minimum |avg return| % required to surface a trade (e.g. 0.5 means ≥ 0.5%)
    avg_return_threshold: float = Field(default=0.0, ge=0.0, le=20.0)
    # Direction filter: ALL, BULL, or BEAR
    direction_filter: Literal["ALL", "BULL", "BEAR"] = "ALL"
    # Min count of traded years (5, 10, 15, 20, 25, or 'max')
    min_years_traded: Optional[Any] = Field(default=None, description="Min count of traded years required")




# ── Response bodies ────────────────────────────────────────────────────────────

class StockInfo(BaseModel):
    symbol: str
    display_name: Optional[str] = None
    data_url: Optional[str] = None
    drive_file_present: bool = False
    drive_file_size_bytes: Optional[int] = None
    drive_file_modified: Optional[str] = None
    last_analysis_at: Optional[str] = None
    added_at: Optional[str] = None
    added_by: Optional[str] = None


class AnalysisRunSummary(BaseModel):
    total_combos: int
    success: int
    errors: int
    details: dict[str, Any]


class UpcomingTrade(BaseModel):
    symbol: str
    view_mode: str
    period: str
    entry_date: str
    exit_date: Optional[str]
    direction: Literal["BULL", "BEAR"]
    pos_prob: float
    neg_prob: Optional[float]
    avg_return: Optional[float]
    sigma: Optional[float]
    streak: int
    days_away: int


class TradeScannerResult(BaseModel):
    symbol: str
    display_name: Optional[str] = None
    label: str                        # e.g. "12-Aug"
    direction: Literal["BULL", "BEAR"]
    pos_prob: float
    neg_prob: float
    avg_return: Optional[float] = None
    sigma: Optional[float] = None
    streak: Optional[int] = None
    count: int                        # years traded on this day
    year_range: Any                   # "max" or int
