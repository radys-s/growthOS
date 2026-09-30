import base64
import io
from datetime import date

import httpx
import pytest
from docx import Document
from fastapi import HTTPException
from pypdf import PdfWriter

from app.growth.imports import document_text, github_text
from app.seed import run as seed

ITEM = {
    "kind": "project",
    "title": "API model",
    "description": "Test result",
    "result": "API tested",
    "url": "https://example.com/evidence",
    "signals": ["deployment"],
    "strength": 3,
    "achieved_on": str(date.today()),
}


def test_import_preview_confirmation_and_dedup(client):
    seed()
    before = client.get("/profile").json()
    first = client.post("/imports/text", json={"text": "Python deployed project"}).json()[0]
    assert first["proposed"]["strength"] == 0
    assert client.get("/profile").json() == before
    again = client.post("/imports/text", json={"text": " Python deployed project "}).json()[0]
    assert again["id"] == first["id"]
    payload = {"item": ITEM, "evidence_kind": "claimed", "confirmed": True}
    result = client.post(f"/imports/{first['id']}/confirm", json=payload)
    assert result.status_code == 200, result.text
    assert result.json()["provenance"]["excerpt"] == "Python deployed project"
    goal = client.get("/goals").json()[0]
    gap = next(
        g for g in client.get(f"/goals/{goal['id']}/gaps").json() if g["signal"] == "deployment"
    )
    assert all(s["item_id"] != result.json()["id"] for s in gap["supports"])
    payload["item"] = {**ITEM, "title": "Changed on retry"}
    assert (
        client.post(f"/imports/{first['id']}/confirm", json=payload).json()["title"]
        == ITEM["title"]
    )
    assert len(client.get("/profile").json()["items"]) == len(before["items"]) + 1
    assert (
        client.post(
            f"/imports/{first['id']}/confirm", json={**payload, "confirmed": False}
        ).status_code
        == 422
    )


def test_completion_changes_gaps_and_preserves_history(client):
    seed()
    client.post("/sources/run")
    candidate = client.get("/recommendations").json()["top"][0]["candidate"]
    goal = next(g for g in client.get("/goals").json() if g["active"])
    path = f"/goals/{goal['id']}/gaps"
    before = next(g["coverage"] for g in client.get(path).json() if g["signal"] == "deployment")
    payload = {
        "target_type": candidate["source"],
        "target_id": candidate["target_id"],
        "item": ITEM,
        "confirmed": True,
        "evidence_kind": "demonstrated",
    }
    response = client.post("/completions", json=payload)
    assert response.status_code == 200, response.text
    assert client.post("/completions", json=payload).json()["id"] == response.json()["id"]
    after = next(g for g in client.get(path).json() if g["signal"] == "deployment")
    assert after["coverage"] > before
    assert any(s["item_id"] == response.json()["id"] for s in after["supports"])
    assert len(client.get("/progress").json()) == 4
    assert len(client.get("/history").json()) == 1
    assert candidate["key"] not in {
        i["candidate"]["key"] for i in client.get("/recommendations").json()["ranked"]
    }
    assert (
        client.delete(f"/decisions/{candidate['source']}/{candidate['target_id']}").status_code
        == 204
    )
    assert len(client.get("/history").json()) == 2
    assert client.get("/history").json()[0]["status"] == "reversed"
    assert any(i["id"] == response.json()["id"] for i in client.get("/profile").json()["items"])
    assert candidate["key"] in {
        i["candidate"]["key"] for i in client.get("/recommendations").json()["ranked"]
    }
    # Completing again after the reversal hides the item again (latest decision, not any "done").
    assert client.post("/completions", json=payload).status_code == 200
    assert client.get("/history").json()[0]["status"] == "done"
    assert candidate["key"] not in {
        i["candidate"]["key"] for i in client.get("/recommendations").json()["ranked"]
    }


def test_demonstrated_import_needs_non_blank_result(client):
    seed()
    proposal = client.post("/imports/text", json={"text": "Kaggle bronze"}).json()[0]
    payload = {
        "item": {**ITEM, "result": "   "},
        "evidence_kind": "demonstrated",
        "confirmed": True,
    }
    assert client.post(f"/imports/{proposal['id']}/confirm", json=payload).status_code == 422


def test_unsupported_and_malformed_imports(client):
    for name, content, status in [
        ("cv.txt", b"hello", 415),
        ("cv.pdf", b"broken", 422),
        ("cv.docx", b"broken", 422),
    ]:
        assert client.post("/imports/file", files={"file": (name, content)}).status_code == status
    assert client.post("/imports/text", json={"text": "  "}).status_code == 422
    pdf = PdfWriter()
    pdf.add_blank_page(width=100, height=100)
    buffer = io.BytesIO()
    pdf.write(buffer)
    response = client.post("/imports/file", files={"file": ("scan.pdf", buffer.getvalue())})
    assert response.status_code == 422
    doc = Document()
    doc.add_paragraph("Python project")
    buffer = io.BytesIO()
    doc.save(buffer)
    assert document_text("cv.docx", buffer.getvalue()).strip() == "Python project"


@pytest.mark.parametrize("status,expected", [(403, 429), (429, 429), (404, 404), (500, 502)])
def test_github_errors(status, expected):
    with (
        httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(status))) as client,
        pytest.raises(HTTPException) as error,
    ):
        github_text("owner/repo", client)
    assert error.value.status_code == expected


def test_github_public_metadata_is_not_mastery(client, monkeypatch):
    def request(req):
        if req.url.path.endswith("/repo"):
            return httpx.Response(
                200, json={"private": False, "description": "Python project", "language": "Python"}
            )
        if req.url.path.endswith("readme"):
            return httpx.Response(
                200,
                json={
                    "type": "file",
                    "encoding": "base64",
                    "size": 20,
                    "content": base64.b64encode(b"Production deployment").decode(),
                },
            )
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(request)) as remote:
        _, _, text = github_text("owner/repo", remote)
    preview = client.post("/imports/text", json={"text": text}).json()
    assert all(p["proposed"]["strength"] == 0 for p in preview)
    assert all("industry_experience" not in p["proposed"]["signals"] for p in preview)
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"private": True}))
        ) as remote,
        pytest.raises(HTTPException),
    ):
        github_text("owner/repo", remote)


def test_week_budget_and_aware_dates(client):
    profile = client.get("/profile").json()
    client.put(
        "/profile",
        json={
            "name": profile["name"],
            "country": "CZ",
            "education_level": "high_school",
            "weekly_hours_budget": 1,
        },
    )
    payload = {
        "title": "Project",
        "est_hours": 3,
        "week_of": "2026-10-25",
        "starts_at": "2026-10-25T02:30:00+02:00",
        "ends_at": "2026-10-25T02:30:00+01:00",
    }
    result = client.post("/plans", json=payload)
    assert result.status_code == 200, result.text
    assert result.json()["week_of"] == "2026-10-19"
    week = client.get("/plans?week_of=2026-10-25").json()
    assert week["over_budget"] and week["planned_hours"] == 3
    assert (
        client.post("/plans", json={**payload, "starts_at": "2026-10-25T02:30:00"}).status_code
        == 422
    )


def test_explicit_useful_metric(client):
    seed()
    client.post("/sources/run")
    result = client.get("/recommendations").json()
    assert result["novelty"]["explicitly_useful"] == 0
    item = result["top"][0]["candidate"]
    client.post(
        "/decisions",
        json={"target_type": item["source"], "target_id": item["target_id"], "status": "useful"},
    )
    assert client.get("/recommendations").json()["novelty"]["explicitly_useful"] == 1


def test_untrusted_origin_cannot_write(client):
    response = client.post(
        "/imports/text", json={"text": "private"}, headers={"Origin": "https://attacker.example"}
    )
    assert response.status_code == 403


def test_useful_feedback_survives_later_decision(client):
    seed()
    client.post("/sources/run")
    candidate = client.get("/recommendations").json()["top"][0]["candidate"]
    target = {"target_type": candidate["source"], "target_id": candidate["target_id"]}
    client.post("/decisions", json={**target, "status": "useful"})
    client.post("/decisions", json={**target, "status": "done"})
    assert client.get("/recommendations").json()["novelty"]["explicitly_useful"] == 1
    client.delete(f"/decisions/{target['target_type']}/{target['target_id']}")
    assert client.get("/recommendations").json()["novelty"]["explicitly_useful"] == 0
