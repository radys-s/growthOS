import pytest

from app.credentials import (
    Credential,
    CredentialType,
    Tier,
    credential_tier,
    goal_fit,
)


@pytest.mark.parametrize(
    ("ctype", "reputation", "fit", "tier"),
    [
        (CredentialType.INDUSTRY_CERTIFICATION, 5, 1.0, Tier.S),
        (CredentialType.INDUSTRY_CERTIFICATION, 5, 0.75, Tier.S),  # boundary is inclusive
        (CredentialType.INDUSTRY_CERTIFICATION, 4, 0.8, Tier.A),  # 0.64
        (CredentialType.INDUSTRY_CERTIFICATION, 5, 0.5, Tier.B),
        (CredentialType.SKILL_BADGE, 5, 1.0, Tier.A),  # 0.6
        (CredentialType.SKILL_BADGE, 3, 1.0, Tier.B),  # 0.36
        (CredentialType.COURSE_CERTIFICATE, 5, 1.0, Tier.B),  # 0.35
        (CredentialType.COURSE_CERTIFICATE, 3, 1.0, Tier.C),  # 0.21
        (CredentialType.PARTICIPATION_BADGE, 5, 1.0, Tier.IGNORE),  # 0.1
        (CredentialType.INDUSTRY_CERTIFICATION, 5, 0.0, Tier.IGNORE),  # off-goal
    ],
)
def test_credential_tier(ctype: CredentialType, reputation: int, fit: float, tier: Tier) -> None:
    result = credential_tier(Credential(type=ctype, issuer_reputation=reputation), fit)
    assert result.tier == tier


def test_goal_fit_discounts_already_covered_signals() -> None:
    assert goal_fit(1.0, 1.0) == 1.0
    assert goal_fit(1.0, 0.0) == 0.5
    assert goal_fit(0.0, 0.0) == 0.0


def test_reputation_is_bounded() -> None:
    with pytest.raises(ValueError):
        Credential(type=CredentialType.SKILL_BADGE, issuer_reputation=6)
