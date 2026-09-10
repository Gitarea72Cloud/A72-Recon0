"""Branching + scoring rules for the Stage 0 / A / B placement flow.

Decisions this encodes (see the project proposal for the full rationale):
  - Thresholds kept at 55% / 70% for Cohort 1 (Oct 2026); recalibrate from
    real data before Cohort 2 (Jan 2027) — this is the one place to change
    them. They still gate ROUTING (how many questions a student sees --
    Stage 0 alone, or a confirmation/tie-break round), just not the final
    Basic/Advanced call any more -- see gaussian_track below.
  - Stage A is always the last step: pass or fail, the combined score
    decides Basic vs. Advanced. No retry, no manual override.
  - v1 domains are Linux-only (see DOMAINS below). Windows/AD stays
    conceptual/free-text until the windows-exec engine exists.
"""
import statistics

STAGE0_LOW_THRESHOLD = 55.0   # below this -> straight to Basic
STAGE0_HIGH_THRESHOLD = 70.0  # at/above this -> Stage A
FINAL_ADVANCED_THRESHOLD = 70.0  # bootstrap-only cutoff, see gaussian_track

DOMAINS = [
    "linux_cli",
    "windows_cli",
    "red_team",
    "blue_team",
    "grey_team",
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


def combine_stage0_and_stage_a(stage0_pct: float, stage_a_pct: float,
                                stage0_weight: float = 0.4, stage_a_weight: float = 0.6) -> float:
    """Stage A is always final: weighted toward Stage A (harder, more
    discriminating) but Stage 0 still counts, so a strong screening score
    provides some cushion. Feeds into gaussian_track below, same as any
    other composite score.
    """
    return stage0_pct * stage0_weight + stage_a_pct * stage_a_weight


MIN_COHORT_SAMPLE = 5  # fewer prior completions than this -> statistics aren't meaningful yet


def gaussian_track(score: float, prior_scores: list[float]) -> str:
    """Basic vs. Advanced by comparing this student's score to the
    distribution of everyone who has *already* completed placement in
    this cohort -- a rolling bell curve, not a fixed absolute bar. At or
    above the running mean -> Advanced, below -> Basic.

    This is deliberately norm-referenced: a cohort that all scores low
    still splits roughly down the middle, because placement here means
    "relative to peers," not "cleared an absolute bar." That's the
    explicit tradeoff of grading on a curve, not an oversight.

    Needs enough prior data to say anything -- with fewer than
    MIN_COHORT_SAMPLE completions, or zero spread in the sample (every
    prior score identical), falls back to the original fixed high
    threshold so the first few students in a cohort still get a sensible
    placement instead of an arbitrary one.
    """
    if len(prior_scores) < MIN_COHORT_SAMPLE:
        return ADVANCED if score >= STAGE0_HIGH_THRESHOLD else BASIC
    mean = statistics.fmean(prior_scores)
    stdev = statistics.pstdev(prior_scores)
    if stdev == 0:
        return ADVANCED if score >= STAGE0_HIGH_THRESHOLD else BASIC
    z = (score - mean) / stdev
    return ADVANCED if z >= 0 else BASIC


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

    security_domains = {"red_team": "Red Team", "blue_team": "Blue Team", "grey_team": "Grey Team/ethics"}
    security_scores = {label: domain_scores[key] for key, label in security_domains.items() if key in domain_scores}
    if len(security_scores) >= 2:
        weakest = min(security_scores, key=security_scores.get)
        strongest = max(security_scores, key=security_scores.get)
        if security_scores[strongest] - security_scores[weakest] >= GAP_THRESHOLD:
            lines.append(
                f"Within security concepts, strongest in {strongest} ({security_scores[strongest]:.0f}%), "
                f"weaker in {weakest} ({security_scores[weakest]:.0f}%) -- worth a conceptual refresher there."
            )
        else:
            lines.append("Even conceptual grounding across Red/Blue/Grey Team topics.")

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
