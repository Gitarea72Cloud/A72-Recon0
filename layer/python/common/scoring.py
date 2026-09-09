"""Branching + scoring rules for the Stage 0 / A / B placement flow.

Decisions this encodes (see the project proposal for the full rationale):
  - Thresholds kept at 55% / 70% for Cohort 1 (Oct 2026); recalibrate from
    real data before Cohort 2 (Jan 2027) — this is the one place to change
    them.
  - Stage A is always the last step: pass or fail, the combined score
    decides Basic vs. Advanced. No retry, no manual override.
  - v1 domains are Linux-only (see DOMAINS below). Windows/AD stays
    conceptual/free-text until the windows-exec engine exists.
"""

STAGE0_LOW_THRESHOLD = 55.0   # below this -> straight to Basic
STAGE0_HIGH_THRESHOLD = 70.0  # at/above this -> Stage A
FINAL_ADVANCED_THRESHOLD = 70.0  # composite Stage0+StageA score needed to land Advanced

DOMAINS = [
    "linux_cli",
    "windows_cli",
    "networking",
    "scripting",
    "core_security",
    "tooling_familiarity",  # Stage A only
]

BASIC = "Basic"
ADVANCED = "Advanced"


def route_after_stage0(stage0_pct: float) -> str:
    """Returns 'basic' | 'stageA' | 'stageB' given the Stage 0 percentage score."""
    if stage0_pct < STAGE0_LOW_THRESHOLD:
        return "basic"
    if stage0_pct >= STAGE0_HIGH_THRESHOLD:
        return "stageA"
    return "stageB"


def finalize_from_stage0_only(stage0_pct: float) -> str:
    """A student routed straight to Basic from Stage 0 — no further stages."""
    return BASIC


def finalize_after_stage_b(stage_b_pct: float) -> str:
    """Stage B is itself the tie-break: pass/fail on the short round alone."""
    return ADVANCED if stage_b_pct >= 50.0 else BASIC


def finalize_after_stage_a(stage0_pct: float, stage_a_pct: float,
                            stage0_weight: float = 0.4, stage_a_weight: float = 0.6) -> str:
    """Stage A is always final: combine both scores and decide once.

    Weighted toward Stage A (harder, more discriminating) but Stage 0 still
    counts, so a strong screening score provides some cushion. Whatever the
    outcome, this is the last stage — no extra round, no manual flag.
    """
    composite = stage0_pct * stage0_weight + stage_a_pct * stage_a_weight
    return ADVANCED if composite >= FINAL_ADVANCED_THRESHOLD else BASIC


def score_domain_answers(answers: list[dict]) -> dict:
    """answers: [{domain, correct: bool}, ...] -> {domain: pct, ..., "_overall": pct}"""
    by_domain: dict[str, list[bool]] = {}
    for a in answers:
        by_domain.setdefault(a["domain"], []).append(bool(a.get("correct")))

    scores = {
        domain: round(100 * sum(vals) / len(vals), 1)
        for domain, vals in by_domain.items()
        if vals
    }
    all_vals = [v for vals in by_domain.values() for v in vals]
    scores["_overall"] = round(100 * sum(all_vals) / len(all_vals), 1) if all_vals else 0.0
    return scores
