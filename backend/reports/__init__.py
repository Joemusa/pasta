"""Commercial Opportunity Pulse V1: PDF presentation layer over frozen agent outputs."""

from backend.reports.assemble import assemble
from backend.reports.loader import load_inputs
from backend.reports.render import render_executive_pdf, render_full_pdf

__all__ = ["assemble", "load_inputs", "render_executive_pdf", "render_full_pdf"]
