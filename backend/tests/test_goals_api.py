from fastapi.testclient import TestClient


def _create(client: TestClient, template_id: str, **extra: object) -> dict:
    response = client.post("/goals", json={"template_id": template_id, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def test_goal_from_template_copies_signals_and_weights(client: TestClient) -> None:
    goal = _create(client, "ai_ml_internship")
    assert goal["title"] == "AI/ML internship 2027"
    assert goal["active"] is True
    assert any(r["signal"] == "deployment" for r in goal["required_signals"])
    assert goal["weights"]["gap_coverage"] == 0.30


def test_only_one_active_goal(client: TestClient) -> None:
    first = _create(client, "ai_ml_internship")
    second = _create(client, "competition_profile")
    goals = {g["id"]: g for g in client.get("/goals").json()}
    assert goals[second["id"]]["active"] is True
    assert goals[first["id"]]["active"] is False

    client.patch(f"/goals/{first['id']}", json={"active": True})
    goals = {g["id"]: g for g in client.get("/goals").json()}
    assert goals[first["id"]]["active"] is True
    assert goals[second["id"]]["active"] is False


def test_first_goal_is_active_even_if_not_requested(client: TestClient) -> None:
    assert _create(client, "competition_profile", active=False)["active"] is True


def test_deleting_active_goal_activates_remaining(client: TestClient) -> None:
    first = _create(client, "ai_ml_internship")
    second = _create(client, "competition_profile")
    assert client.delete(f"/goals/{second['id']}").status_code == 204
    goals = client.get("/goals").json()
    assert [g["id"] for g in goals] == [first["id"]]
    assert goals[0]["active"] is True


def test_patch_required_signals_validates_taxonomy(client: TestClient) -> None:
    goal = _create(client, "ai_ml_internship")
    bad = client.patch(
        f"/goals/{goal['id']}", json={"required_signals": [{"signal": "nope", "importance": 2}]}
    )
    assert bad.status_code == 422
    ok = client.patch(
        f"/goals/{goal['id']}", json={"required_signals": [{"signal": "cloud", "importance": 3}]}
    )
    assert ok.json()["required_signals"] == [{"signal": "cloud", "importance": 3}]


def test_unknown_template_is_422(client: TestClient) -> None:
    assert client.post("/goals", json={"template_id": "astronaut"}).status_code == 422
