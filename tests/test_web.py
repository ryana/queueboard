from fastapi.testclient import TestClient


def test_dashboard_create_edit_and_delete_flow(client: TestClient) -> None:
    empty_dashboard = client.get("/")
    assert empty_dashboard.status_code == 200
    assert "The queue is clear" in empty_dashboard.text

    created = client.post(
        "/work-items",
        data={
            "title": "Prepare weekly update",
            "description": "Summarize **shipped work**\n\n<script>alert('no')</script>",
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    location = created.headers["location"]

    detail = client.get(location)
    assert "Prepare weekly update" in detail.text
    assert "<strong>shipped work</strong>" in detail.text
    assert "<script>" not in detail.text
    assert "&lt;script&gt;alert('no')&lt;/script&gt;" in detail.text
    assert "Work item created" in detail.text

    updated = client.post(
        location,
        data={
            "title": "Publish weekly update",
            "description": "Summarize shipped work",
            "status": "done",
            "priority": "medium",
        },
        follow_redirects=False,
    )
    assert updated.status_code == 303

    dashboard = client.get("/")
    assert "Publish weekly update" in dashboard.text
    assert "status-done" in dashboard.text

    deleted = client.post(f"{location}/delete", follow_redirects=False)
    assert deleted.status_code == 303
    assert "The queue is clear" in client.get("/").text
