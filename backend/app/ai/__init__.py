"""Provider-independent AI routing analysis (Phase 3)."""

from app.ai.factory import get_ai_provider
from app.ai.schemas import AIRoutingRecommendation

__all__ = ["AIRoutingRecommendation", "get_ai_provider"]
