import csv
import io

from fastapi.testclient import TestClient

from queueboard.bulk_csv import CSV_HEADERS, MAX_IMPORT_ROWS, MAX_UPLOAD_BYTES


def csv_upload(contents: str) -> dict[str, tuple[str, bytes, str]]:
    return {"upload": ("work-items.csv", contents.encode(), "text/csv")}


def test_export_is_stable_and_spreadsheet_safe(client: TestClient) -> None:
    created = client.post(
        "/api/work-items",
        json={
            "title": "=SUM(A1:A2)",
            "description": "First line\nSecond line",
            "status": "in_progress",
            "priority": "high",
        },
    )
    assert created.status_code == 201

    response = client.get("/api/work-items/export.csv")

    assert response.status_code == 200
    assert response.content.startswith(b"\xef\xbb\xbf")
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert response.headers["content-disposition"] == (
        'attachment; filename="queueboard-work-items.csv"'
    )
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert tuple(rows[0]) == CSV_HEADERS
    assert rows[0]["title"] == "'=SUM(A1:A2)"
    assert rows[0]["description"] == "First line\nSecond line"
    assert rows[0]["status"] == "in_progress"
    assert rows[0]["priority"] == "high"
    assert rows[0]["created_at"]
    assert rows[0]["updated_at"]


def test_valid_import_is_atomic_and_records_activity(client: TestClient) -> None:
    contents = (
        "id,title,description,status,priority,created_at,updated_at\n"
        '44,"Imported, one","First line",todo,high,2025-01-01,2025-01-01\n'
        '45,"Imported two","Second line",done,low,2025-01-01,2025-01-01\n'
    )

    response = client.post("/api/work-items/import.csv", files=csv_upload(contents))

    assert response.status_code == 201
    assert response.json()["imported"] == 2
    imported_ids = response.json()["ids"]
    assert len(imported_ids) == 2
    items = client.get("/api/work-items").json()
    assert {item["title"] for item in items} == {"Imported, one", "Imported two"}
    detail = client.get(f"/api/work-items/{imported_ids[0]}").json()
    assert detail["activities"][0]["message"] == "Work item imported from CSV"


def test_invalid_import_reports_rows_and_creates_nothing(client: TestClient) -> None:
    contents = (
        "title,description,status,priority\nValid row,,todo,medium\nInvalid row,,waiting,urgent\n"
    )

    response = client.post("/api/work-items/import.csv", files=csv_upload(contents))

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert {error["field"] for error in errors} == {"status", "priority"}
    assert {error["row"] for error in errors} == {3}
    assert client.get("/api/work-items").json() == []


def test_import_limits_are_enforced(client: TestClient) -> None:
    oversized = client.post(
        "/api/work-items/import.csv",
        files={"upload": ("large.csv", b"x" * (MAX_UPLOAD_BYTES + 1), "text/csv")},
    )
    assert oversized.status_code == 422
    assert "limit" in oversized.json()["detail"][0]["message"]

    rows = "".join(f"Item {number},,todo,medium\n" for number in range(MAX_IMPORT_ROWS + 1))
    too_many = client.post(
        "/api/work-items/import.csv",
        files=csv_upload("title,description,status,priority\n" + rows),
    )
    assert too_many.status_code == 422
    assert "more than 500" in too_many.json()["detail"][0]["message"]
    assert client.get("/api/work-items").json() == []


def test_import_rejects_invalid_files_and_headers(client: TestClient) -> None:
    cases = [
        (b"", "empty"),
        (b"\xff\xfe\x00", "UTF-8"),
        (b'title,status\n"unterminated,todo\n', "malformed"),
        (b"status,priority\ntodo,medium\n", "title column is required"),
        (b"title,title\nOne,Two\n", "Duplicate columns"),
        (b"title,,status\nOne,,todo\n", "Column names cannot be empty"),
        (b"title,owner\nOne,Ryan\n", "Unknown columns"),
        (b"title,status\nOne,todo,extra\n", "more values than headers"),
        (b"title,description\nOne,contains\x00null\n", "Null bytes"),
    ]

    for contents, expected_message in cases:
        response = client.post(
            "/api/work-items/import.csv",
            files={"upload": ("invalid.csv", contents, "text/csv")},
        )
        assert response.status_code == 422
        messages = " ".join(error["message"] for error in response.json()["detail"])
        assert expected_message in messages

    assert client.get("/api/work-items").json() == []


def test_web_import_flow_reports_success_and_errors(client: TestClient) -> None:
    dashboard = client.get("/")
    assert 'action="/work-items/import"' in dashboard.text
    assert 'href="/api/work-items/export.csv"' in dashboard.text

    imported = client.post(
        "/work-items/import",
        files=csv_upload("title,description,status,priority\nWeb import,,todo,medium\n"),
    )
    assert imported.status_code == 200
    assert "work item imported successfully" in imported.text
    assert "<strong>1</strong>" in imported.text
    assert "Web import" in imported.text

    rejected = client.post(
        "/work-items/import",
        files=csv_upload("title,status\nBroken,unknown\n"),
    )
    assert rejected.status_code == 422
    assert "No work items were imported" in rejected.text
    assert "Row 2 · status" in rejected.text
