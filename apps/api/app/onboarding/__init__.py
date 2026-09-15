"""Stage 0 restaurant onboarding capture and analysis contract."""

from app.onboarding.analyzer import AnalysisResult, analyze_xlsx
from app.onboarding.contract import CONTRACT_VERSION, ONBOARDING_CONTRACT

__all__ = ["AnalysisResult", "CONTRACT_VERSION", "ONBOARDING_CONTRACT", "analyze_xlsx"]
