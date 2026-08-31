"""Commercial Intelligence Dashboard V1: presentation layer over frozen agent outputs."""

from backend.dashboard.loader import DashboardStore, load_store
from backend.dashboard.query import assemble, opportunity_detail

__all__ = ["DashboardStore", "assemble", "load_store", "opportunity_detail"]
