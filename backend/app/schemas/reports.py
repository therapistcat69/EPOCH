"""Structured outputs. Groq models validate against the Groq* classes; everything else is deterministic."""
from typing import Literal

from pydantic import BaseModel, Field


# ------------------------------------------------------------------ Groq output (validated)
class Insight(BaseModel):
    """Keeps evidence-based reasoning separate: observation (data) -> interpretation -> recommendation."""

    observation: str = ""
    interpretation: str = ""
    recommendation: str = ""


class GroqChannelReport(BaseModel):
    summary: str
    strengths: list[str] = []
    weaknesses: list[str] = []
    content_patterns: list[str] = []
    observed_performance_patterns: list[str] = []
    recommendations: list[Insight] = []
    experiments_to_try: list[str] = []


class VideoRecommendation(BaseModel):
    type: Literal["cut", "tighten", "move", "test", "add", "rewrite", "other"] = "other"
    start: float | None = None
    end: float | None = None
    reason: str
    evidence: str
    confidence: float | None = Field(None, ge=0, le=1)  # the model's own judgement, not a statistic


class GroqVideoReport(BaseModel):
    summary: str
    strengths: list[str] = []
    weaknesses: list[str] = []
    hook_analysis: Insight = Insight()
    pacing_analysis: Insight = Insight()
    repetition_analysis: Insight = Insight()
    title_alignment: Insight = Insight()
    recommendations: list[VideoRecommendation] = []


class TrendOpportunity(BaseModel):
    title: str
    evidence: list[str] = []
    suggested_experiment: str = ""


class GroqTrendReport(BaseModel):
    summary: str
    observed_opportunities: list[TrendOpportunity] = []
    caveats: list[str] = []


class SectionLabel(BaseModel):
    index: int
    topic: str
    summary: str


class SectionLabels(BaseModel):
    sections: list[SectionLabel]


class RiskExplanation(BaseModel):
    start_seconds: float
    end_seconds: float
    what_is_happening: str
    possible_experiment: str


class GroqMLExplanation(BaseModel):
    """Natural-language explanation of the ML model's output. Groq never changes the model's numbers."""

    summary: str
    risk_explanations: list[RiskExplanation] = []


# ------------------------------------------------------------------ envelope helpers
class GroqStatus(BaseModel):
    available: bool
    reason: str | None = None  # e.g. "GROQ_NOT_CONFIGURED"
    message: str | None = None
