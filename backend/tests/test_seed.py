from sqlalchemy.orm import Session

from app.goals.service import get_active_goal, list_goals
from app.profile.service import signal_coverage
from app.seed import seed_goals, seed_profile


def test_seed_is_idempotent(session: Session) -> None:
    profile, created = seed_profile(session)
    assert created
    assert seed_goals(session, profile) == 2

    again, created_again = seed_profile(session)
    assert not created_again and again.id == profile.id
    assert seed_goals(session, profile) == 0
    assert len(list_goals(session, profile)) == 2

    active = get_active_goal(session, profile)
    assert active is not None and active.template_id == "ai_ml_internship"


def test_coverage_uses_best_of_skill_and_items(session: Session) -> None:
    profile, _ = seed_profile(session)
    coverage = signal_coverage(profile)
    assert coverage["ml_competition_result"] == 0.75  # item strength 3
    assert coverage["classical_ml"] == 0.75  # skill 3, item 3
    assert "research_evidence" not in coverage


def test_invalid_seed_file_writes_nothing(session: Session, monkeypatch, tmp_path) -> None:
    import pytest

    import app.seed as seed_module

    (tmp_path / "seed").mkdir()
    (tmp_path / "seed" / "profile.yaml").write_text(
        "name: X\ncountry: CZ\neducation_level: high_school\n"
        "skills: [{signal: python, level: 2}]\n"
        "items: [{kind: project, title: Y, signals: [nonsense], strength: 1}]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(seed_module, "DATA_DIR", tmp_path)
    with pytest.raises(ValueError):
        seed_profile(session)
    session.rollback()
    from app.profile.service import get_profile

    assert get_profile(session) is None
