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
