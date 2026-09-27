import pytest

from app.taxonomy import load_goal_templates, load_taxonomy


def test_aliases_resolve_to_canonical_ids() -> None:
    taxonomy = load_taxonomy()
    assert taxonomy.resolve("PyTorch") == "deep_learning"
    assert taxonomy.resolve("scikit-learn") == "classical_ml"
    assert taxonomy.resolve("deployment") == "deployment"


def test_unknown_signal_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown signal"):
        load_taxonomy().resolve("underwater_basket_weaving")


def test_goal_templates_load_and_reference_known_signals() -> None:
    templates = load_goal_templates()
    assert {"ai_ml_internship", "competition_profile"} <= set(templates)
    known = set(load_taxonomy().by_id)
    for template in templates.values():
        assert {r.signal for r in template.required_signals} <= known
