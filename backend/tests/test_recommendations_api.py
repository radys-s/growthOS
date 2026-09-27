import uuid

import pytest
from fastapi.testclient import TestClient

from app.seed import run as run_seed


@pytest.fixture
def seeded(client: TestClient) -> TestClient:
    run_seed()
    assert client.post("/sources/run").status_code == 200
    return client


def _active_goal(client: TestClient) -> dict:
    return next(g for g in client.get("/goals").json() if g["active"])


def test_recommendations_top5_with_explanations(seeded: TestClient) -> None:
    response = seeded.get("/recommendations")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["goal_id"] == _active_goal(seeded)["id"]
    top = body["top"]
    assert len(top) == 5
    kinds = [item["candidate"]["kind"] for item in top]
    assert all(kinds.count(k) <= 2 for k in kinds)
    for item in top:
        assert set(item["factors"]) == set(item["contributions"])
        assert item["priority"] == pytest.approx(sum(item["contributions"].values()), abs=1e-3)
        assert item["candidate"]["target_id"]
        assert item["reasons"], item["candidate"]["title"]
    priorities = [i["priority"] for i in body["ranked"]]
    assert priorities == sorted(priorities, reverse=True)
    assert body["novelty"]["new_items"] == len(body["ranked"]) + len(body["filtered"])


def test_recommendations_are_deterministic(seeded: TestClient) -> None:
    first = seeded.get("/recommendations").json()["ranked"]
    second = seeded.get("/recommendations").json()["ranked"]
    assert [i["candidate"]["key"] for i in first] == [i["candidate"]["key"] for i in second]


def test_other_goal_changes_ranking(seeded: TestClient) -> None:
    other = next(g for g in seeded.get("/goals").json() if not g["active"])
    active = seeded.get("/recommendations").json()
    competition = seeded.get(f"/recommendations?goal_id={other['id']}").json()
    assert competition["goal_id"] == other["id"]
    assert [i["priority"] for i in active["ranked"]] != [
        i["priority"] for i in competition["ranked"]
    ]


def test_recommendations_without_goal_404(client: TestClient) -> None:
    assert client.get("/recommendations").status_code == 404
    assert client.get(f"/recommendations?goal_id={uuid.uuid4()}").status_code == 404


def test_goal_gaps(seeded: TestClient) -> None:
    goal = _active_goal(seeded)
    gaps = seeded.get(f"/goals/{goal['id']}/gaps").json()
    assert len(gaps) == len(goal["required_signals"])
    assert [g["gap"] for g in gaps] == sorted((g["gap"] for g in gaps), reverse=True)
    assert all(g["label"] for g in gaps)
    assert seeded.get(f"/goals/{uuid.uuid4()}/gaps").status_code == 404


def test_decision_hides_item_and_latest_wins(seeded: TestClient) -> None:
    item = seeded.get("/recommendations").json()["top"][0]["candidate"]
    payload = {"target_type": item["source"], "target_id": item["target_id"]}

    done = seeded.post("/decisions", json={**payload, "status": "done"})
    assert done.status_code == 201, done.text
    body = seeded.get("/recommendations").json()
    assert item["key"] not in {i["candidate"]["key"] for i in body["ranked"]}
    hidden = next(f for f in body["filtered"] if f["candidate"]["key"] == item["key"])
    assert hidden["reason"] == "Rozhodnuto: hotovo"

    seeded.post("/decisions", json={**payload, "status": "planned"})
    body = seeded.get("/recommendations").json()
    back = next(i for i in body["ranked"] if i["candidate"]["key"] == item["key"])
    assert back["candidate"]["decision"] == "planned"
    assert len(seeded.get("/decisions").json()) == 2


def test_already_knew_stays_but_not_new_worthwhile(seeded: TestClient) -> None:
    before = seeded.get("/recommendations").json()
    item = before["top"][0]["candidate"]
    seeded.post(
        "/decisions",
        json={
            "target_type": item["source"],
            "target_id": item["target_id"],
            "status": "already_knew",
        },
    )
    after = seeded.get("/recommendations").json()
    assert item["key"] in {i["candidate"]["key"] for i in after["ranked"]}
    assert after["novelty"]["already_knew"] == 1
    assert after["novelty"]["new_worthwhile"] == before["novelty"]["new_worthwhile"] - 1


def test_decision_validation(seeded: TestClient) -> None:
    missing = {"target_type": "action", "target_id": str(uuid.uuid4()), "status": "done"}
    assert seeded.post("/decisions", json=missing).status_code == 404
    item = seeded.get("/recommendations").json()["top"][0]["candidate"]
    bad = {"target_type": item["source"], "target_id": item["target_id"], "status": "maybe"}
    assert seeded.post("/decisions", json=bad).status_code == 422
