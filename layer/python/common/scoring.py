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

HINT_PENALTY = 0.33  # each hint used costs 33% of that item's credit


def credit_for(correct: bool, hints_used: int) -> float:
    """A correct answer is worth less credit the more hints it took.

    0 hints -> 1.0, 1 -> 0.67, 2 -> 0.34, 3+ -> ~0. A wrong answer is
    always 0 regardless of hints -- hints reduce credit, they don't
    create it.
    """
    if not correct:
        return 0.0
    return round(max(0.0, 1.0 - HINT_PENALTY * hints_used), 2)


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


GAP_THRESHOLD = 15.0  # domain-score spread beyond which we call out an imbalance


def recommend(domain_scores: dict, track: str) -> str:
    """A short, rule-based read on a student's profile for the instructor
    dashboard -- not a model call, just the same kind of if/else this
    module already uses for placement itself. Meant as a starting point
    for a human reading a cohort report, not a final verdict.
    """
    linux = domain_scores.get("linux_cli")
    windows = domain_scores.get("windows_cli")
    overall = domain_scores.get("_overall", 0.0)

    lines = []
    if linux is not None and windows is not None:
        gap = linux - windows
        if abs(gap) < GAP_THRESHOLD:
            lines.append("Roughly even performance across Linux and PowerShell.")
        elif gap > 0:
            lines.append(
                f"Comfortable with Linux ({linux:.0f}%) but noticeably weaker in PowerShell "
                f"({windows:.0f}%) -- targeted PowerShell/Windows practice recommended before Module 1."
            )
        else:
            lines.append(
                f"Comfortable with PowerShell ({windows:.0f}%) but noticeably weaker in Linux "
                f"({linux:.0f}%) -- targeted Linux CLI practice recommended before Module 1."
            )

    if overall >= 85:
        lines.append("Consistently strong overall -- a good candidate to move quickly, possibly a peer-mentor fit.")
    elif overall < STAGE0_LOW_THRESHOLD:
        lines.append("Below the general screening line across the board -- likely needs the full Basic-track support structure, not just one weak domain.")

    if not lines:
        lines.append(f"Placed {track} on composite score alone; no domain imbalance detected.")

    return " ".join(lines)


def score_domain_answers(answers: list[dict]) -> dict:
    """answers: [{domain, credit: float 0..1}, ...] -> {domain: pct, ..., "_overall": pct}

    `credit` (see credit_for above) already folds in the hint penalty;
    falls back to the plain correct/incorrect boolean for any answer
    recorded before hints existed.
    """
    by_domain: dict[str, list[float]] = {}
    for a in answers:
        credit = a["credit"] if "credit" in a else (1.0 if a.get("correct") else 0.0)
        by_domain.setdefault(a["domain"], []).append(credit)

    scores = {
        domain: round(100 * sum(vals) / len(vals), 1)
        for domain, vals in by_domain.items()
        if vals
    }
    all_vals = [v for vals in by_domain.values() for v in vals]
    scores["_overall"] = round(100 * sum(all_vals) / len(all_vals), 1) if all_vals else 0.0
    return scores
