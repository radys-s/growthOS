"""Credential type classification and S/A/B/C/Ignore tiering (docs/scoring.md §6).

Pure functions: the tier is computed from curated facts (type, issuer reputation) and how well the
credential fits the active goal. No LLM, no clock.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class CredentialType(StrEnum):
    INDUSTRY_CERTIFICATION = "industry_certification"  # proctored exam by a known vendor/body
    SKILL_BADGE = "skill_badge"  # hands-on graded lab / assessment
    COURSE_CERTIFICATE = "course_certificate"  # completion of a course
    PARTICIPATION_BADGE = "participation_badge"  # attendance only


class Tier(StrEnum):
    S = "S"
    A = "A"
    B = "B"
    C = "C"
    IGNORE = "ignore"


TYPE_WEIGHT = {
    CredentialType.INDUSTRY_CERTIFICATION: 1.0,
    CredentialType.SKILL_BADGE: 0.6,
    CredentialType.COURSE_CERTIFICATE: 0.35,
    CredentialType.PARTICIPATION_BADGE: 0.1,
}
THRESHOLDS = ((Tier.S, 0.75), (Tier.A, 0.55), (Tier.B, 0.35), (Tier.C, 0.2))


class Credential(BaseModel):
    type: CredentialType
    issuer_reputation: int = Field(ge=1, le=5, description="1 unknown issuer … 5 industry leader")


class CredentialTier(BaseModel):
    tier: Tier
    score: float


def goal_fit(relevance: float, gap_coverage: float) -> float:
    """On-goal share of the credential's signals, discounted when it covers no open gap."""
    return (relevance + gap_coverage) / 2


def credential_tier(credential: Credential, fit: float) -> CredentialTier:
    score = TYPE_WEIGHT[credential.type] * credential.issuer_reputation / 5 * fit
    tier = next((t for t, threshold in THRESHOLDS if score >= threshold), Tier.IGNORE)
    return CredentialTier(tier=tier, score=round(score, 4))
