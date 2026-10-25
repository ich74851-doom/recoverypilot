"""Contextual severity scoring.

The rule decides *what* went wrong; scoring decides *how urgent* it is for this client
right now. Every point is recorded in a :class:`~recoverypilot.models.ScoreComponent` so a
technician (or an auditor) can see exactly why something is a P1.

Score (0-100) = rule severity base (0-80)
              + RPO breach (10, plus up to 10 more as the breach grows)
              + failure streak (5 per consecutive failure after the first, max 15)
              + client tier (tier 1: +10, tier 2: +5)
"""

from __future__ import annotations

from recoverypilot.config import PriorityThresholds
from recoverypilot.models import Priority, ScoreComponent, Severity
from recoverypilot.rules import JobContext

_TIER_POINTS = {1: 10, 2: 5, 3: 0}


def score_finding(
    severity: Severity, ctx: JobContext, tier: int
) -> tuple[int, list[ScoreComponent]]:
    """Compute the score and its explainable breakdown."""
    parts = [ScoreComponent(factor="severity", points=severity.weight, detail=severity.value)]

    if ctx.rpo_breached:
        extra = 0
        if ctx.hours_since_success is not None and ctx.rpo_hours > 0:
            overrun = ctx.hours_since_success / ctx.rpo_hours - 1
            extra = max(0, min(10, int(overrun * 5)))
        else:
            extra = 10
        parts.append(
            ScoreComponent(
                factor="rpo_breach",
                points=10 + extra,
                detail=(
                    f"{ctx.hours_since_success:.1f}h since success vs RPO {ctx.rpo_hours:g}h"
                    if ctx.hours_since_success is not None
                    else f"no successful run on record (RPO {ctx.rpo_hours:g}h)"
                ),
            )
        )

    if ctx.consecutive_failures > 1:
        parts.append(
            ScoreComponent(
                factor="failure_streak",
                points=min(15, 5 * (ctx.consecutive_failures - 1)),
                detail=f"{ctx.consecutive_failures} consecutive failures",
            )
        )

    tier_points = _TIER_POINTS.get(tier, 0)
    if tier_points:
        parts.append(
            ScoreComponent(factor="client_tier", points=tier_points, detail=f"tier {tier}")
        )

    total = max(0, min(100, sum(p.points for p in parts)))
    return total, parts


def priority_for(score: int, thresholds: PriorityThresholds) -> Priority:
    """Map a score onto a P1-P4 band."""
    if score >= thresholds.p1:
        return Priority.P1
    if score >= thresholds.p2:
        return Priority.P2
    if score >= thresholds.p3:
        return Priority.P3
    return Priority.P4
