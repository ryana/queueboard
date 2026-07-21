from fastapi.testclient import TestClient


def test_health_and_openapi_are_available(client: TestClient) -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["revision"] == "dev"

    docs = client.get("/openapi.json")
    assert docs.status_code == 200
    assert docs.json()["info"]["title"] == "Queueboard"


def test_work_item_crud_and_worker_activity(client: TestClient) -> None:
    created = client.post(
        "/api/work-items",
        json={"title": "Review launch checklist", "priority": "high"},
    )
    assert created.status_code == 201
    item_id = created.json()["id"]

    detail = client.get(f"/api/work-items/{item_id}")
    assert detail.status_code == 200
    assert detail.json()["activities"][0]["message"] == "Work item created"

    updated = client.patch(
        f"/api/work-items/{item_id}",
        json={"status": "in_progress", "description": "Check owners and dates."},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "in_progress"

    filtered = client.get("/api/work-items", params={"status": "in_progress"})
    assert [item["id"] for item in filtered.json()] == [item_id]

    detail = client.get(f"/api/work-items/{item_id}")
    assert len(detail.json()["activities"]) == 2

    deleted = client.delete(f"/api/work-items/{item_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/work-items/{item_id}").status_code == 404


def test_api_rejects_invalid_work_item(client: TestClient) -> None:
    response = client.post("/api/work-items", json={"title": "", "priority": "critical"})
    assert response.status_code == 422
