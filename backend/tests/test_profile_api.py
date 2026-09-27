from fastapi.testclient import TestClient


def test_profile_is_created_on_first_read(client: TestClient) -> None:
    body = client.get("/profile").json()
    assert body["name"] == "Já"
    assert body["skills"] == [] and body["items"] == []


def test_update_profile_fields(client: TestClient) -> None:
    payload = {
        "name": "Tomáš",
        "birth_date": "2009-05-01",
        "country": "cz",
        "education_level": "high_school",
        "max_cost_eur": 100,
        "weekly_hours_budget": 8,
    }
    body = client.put("/profile", json=payload).json()
    assert body["country"] == "CZ"
    assert body["birth_date"] == "2009-05-01"


def test_skills_are_replaced_and_aliases_normalized(client: TestClient) -> None:
    client.put("/profile/skills", json=[{"signal": "python", "level": 3}])
    body = client.put(
        "/profile/skills",
        json=[{"signal": "PyTorch", "level": 2}, {"signal": "fastapi", "level": 1}],
    ).json()
    assert {(s["signal"], s["level"]) for s in body["skills"]} == {
        ("deep_learning", 2),
        ("production_backend", 1),
    }


def test_unknown_skill_signal_is_422(client: TestClient) -> None:
    response = client.put("/profile/skills", json=[{"signal": "nonsense", "level": 2}])
    assert response.status_code == 422


def test_items_add_and_delete(client: TestClient) -> None:
    created = client.post(
        "/profile/items",
        json={
            "kind": "competition",
            "title": "Kaggle",
            "signals": ["kaggle_result", "sklearn"],
            "strength": 3,
            "achieved_on": "2026-05-01",
            "url": "https://www.kaggle.com",
        },
    )
    assert created.status_code == 201
    item = created.json()
    assert item["signals"] == ["ml_competition_result", "classical_ml"]

    assert client.delete(f"/profile/items/{item['id']}").status_code == 204
    assert client.get("/profile").json()["items"] == []
    assert client.delete(f"/profile/items/{item['id']}").status_code == 404


def test_taxonomy_endpoint(client: TestClient) -> None:
    ids = {s["id"] for s in client.get("/taxonomy").json()}
    assert "deployment" in ids
