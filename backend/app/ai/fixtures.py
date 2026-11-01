"""Mock AI fixtures for the six mandatory routing scenarios."""

from __future__ import annotations

from app.ai.schemas import AIRoutingRecommendation

# Scenario catalog used by MockAIProvider keyword matching and tests.
SCENARIOS: dict[str, AIRoutingRecommendation] = {
    "scenario_1_it": AIRoutingRecommendation(
        recommended_department_code="IT",
        confidence=0.92,
        rationale="Hardware/access/systems language indicates Information Technology.",
        is_hr_sensitive=False,
        scenario_id="scenario_1_it",
        labels=["it", "access"],
    ),
    "scenario_2_hr": AIRoutingRecommendation(
        recommended_department_code="HR",
        confidence=0.95,
        rationale="People/relations or sensitive employment content belongs to HR.",
        is_hr_sensitive=True,
        scenario_id="scenario_2_hr",
        labels=["hr", "sensitive"],
    ),
    "scenario_3_finance": AIRoutingRecommendation(
        recommended_department_code="FIN",
        confidence=0.90,
        rationale="Invoice, budget, or expense language maps to Finance.",
        is_hr_sensitive=False,
        scenario_id="scenario_3_finance",
        labels=["finance"],
    ),
    "scenario_4_fleet": AIRoutingRecommendation(
        recommended_department_code="FLEET",
        confidence=0.91,
        rationale="Vehicle/fleet/dealer logistics maps to Fleet Operations.",
        is_hr_sensitive=False,
        scenario_id="scenario_4_fleet",
        labels=["fleet", "vehicle"],
    ),
    "scenario_5_legal": AIRoutingRecommendation(
        recommended_department_code="LEGAL",
        confidence=0.89,
        rationale="Contract/compliance/policy exception language maps to Legal.",
        is_hr_sensitive=False,
        scenario_id="scenario_5_legal",
        labels=["legal", "compliance"],
    ),
    "scenario_6_ambiguous": AIRoutingRecommendation(
        recommended_department_code=None,
        confidence=0.28,
        rationale="Request is too vague to recommend a department with confidence.",
        is_hr_sensitive=False,
        scenario_id="scenario_6_ambiguous",
        labels=["ambiguous", "low_confidence"],
    ),
}

# Keyword heuristics (title+description, lowercased) → scenario id
_KEYWORD_RULES: list[tuple[str, tuple[str, ...]]] = [
    (
        "scenario_2_hr",
        (
            "harassment",
            "payroll dispute",
            "employee relations",
            "medical leave",
            "hr case",
            "compensation dispute",
        ),
    ),
    (
        "scenario_3_finance",
        ("invoice", "budget", "expense", "purchase order", "reimbursement", "vendor payment"),
    ),
    (
        "scenario_4_fleet",
        ("vehicle", "fleet", "tire", "dealer lot", "pool car", "maintenance schedule"),
    ),
    (
        "scenario_5_legal",
        ("contract", "nda", "compliance", "legal review", "policy exception", "liability"),
    ),
    (
        "scenario_1_it",
        (
            "laptop",
            "password",
            "vpn",
            "software",
            "badge access",
            "wifi",
            "email account",
            "printer",
            "hardware",
        ),
    ),
]


def match_scenario(title: str, description: str) -> AIRoutingRecommendation:
    text = f"{title}\n{description}".lower()
    for scenario_id, keywords in _KEYWORD_RULES:
        if any(k in text for k in keywords):
            return SCENARIOS[scenario_id].model_copy(deep=True)
    return SCENARIOS["scenario_6_ambiguous"].model_copy(deep=True)


def scenario_sample_inputs() -> dict[str, tuple[str, str]]:
    """Canonical title/description pairs for scenarios 1–6 (tests/docs)."""
    return {
        "scenario_1_it": (
            "VPN access broken after password reset",
            "I cannot connect to the corporate VPN since resetting my password yesterday.",
        ),
        "scenario_2_hr": (
            "Employee relations concern",
            "I need to report a harassment issue involving my team lead for HR case review.",
        ),
        "scenario_3_finance": (
            "Vendor invoice not paid",
            "Please process the overdue invoice for parts supplier ACME; purchase order PO-4412.",
        ),
        "scenario_4_fleet": (
            "Pool vehicle tire rotation",
            "Need tire rotation scheduled for fleet pool car V-204 before the next dealer run.",
        ),
        "scenario_5_legal": (
            "NDA review for supplier",
            "Legal review requested for a new supplier NDA and compliance checklist.",
        ),
        "scenario_6_ambiguous": (
            "Need help",
            "Something is wrong and someone should look into it when possible.",
        ),
    }
