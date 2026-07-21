import csv
import io
from datetime import datetime

from sqlalchemy.orm import Session

from queueboard.models import WorkItem
from queueboard.tasks import record_activity

CSV_HEADERS = ("id", "title", "description", "status", "priority", "created_at", "updated_at")
KNOWN_HEADERS = frozenset(CSV_HEADERS)
VALID_STATUSES = frozenset({"todo", "in_progress", "done"})
VALID_PRIORITIES = frozenset({"low", "medium", "high"})
MAX_UPLOAD_BYTES = 256 * 1024
MAX_IMPORT_ROWS = 500

CsvError = dict[str, int | str]
CsvRow = dict[str, str]


def make_csv_error(row: int, field: str, message: str) -> CsvError:
    return {"row": row, "field": field, "message": message}


def spreadsheet_safe(value: str) -> str:
    stripped = value.lstrip()
    if stripped.startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r")):
        return f"'{value}"
    return value


def format_csv_datetime(value: datetime) -> str:
    return value.isoformat()


def work_item_to_csv_row(item: WorkItem) -> list[str]:
    return [
        str(item.id),
        spreadsheet_safe(item.title),
        spreadsheet_safe(item.description),
        item.status,
        item.priority,
        format_csv_datetime(item.created_at),
        format_csv_datetime(item.updated_at),
    ]


def write_csv_document(rows: list[list[str]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(CSV_HEADERS)
    writer.writerows(rows)
    return output.getvalue()


def export_work_items_csv(items: list[WorkItem]) -> bytes:
    rows = [work_item_to_csv_row(item) for item in items]
    return ("\ufeff" + write_csv_document(rows)).encode()


def decode_csv_upload(contents: bytes) -> tuple[str | None, list[CsvError]]:
    if not contents:
        return None, [make_csv_error(1, "file", "The uploaded CSV is empty")]
    if len(contents) > MAX_UPLOAD_BYTES:
        return None, [
            make_csv_error(
                1,
                "file",
                f"The uploaded CSV exceeds the {MAX_UPLOAD_BYTES // 1024} KiB limit",
            )
        ]
    try:
        return contents.decode("utf-8-sig"), []
    except UnicodeDecodeError:
        return None, [make_csv_error(1, "file", "The uploaded CSV must use UTF-8 encoding")]


def read_csv_document(source: str) -> tuple[list[list[str]], list[CsvError]]:
    try:
        return list(csv.reader(io.StringIO(source, newline=""), strict=True)), []
    except csv.Error as error:
        return [], [make_csv_error(1, "file", f"The uploaded CSV is malformed: {error}")]


def normalize_csv_header(value: str) -> str:
    return value.strip().lower()


def normalize_csv_headers(values: list[str]) -> list[str]:
    return [normalize_csv_header(value) for value in values]


def find_duplicate_headers(headers: list[str]) -> list[str]:
    return sorted({header for header in headers if headers.count(header) > 1})


def validate_csv_headers(headers: list[str]) -> list[CsvError]:
    errors: list[CsvError] = []
    if not headers or not any(headers):
        return [make_csv_error(1, "header", "The CSV must include a header row")]
    if "" in headers:
        errors.append(make_csv_error(1, "header", "Column names cannot be empty"))
    duplicates = find_duplicate_headers(headers)
    if duplicates:
        errors.append(make_csv_error(1, "header", f"Duplicate columns: {', '.join(duplicates)}"))
    unknown = sorted(set(headers) - KNOWN_HEADERS - {""})
    if unknown:
        errors.append(make_csv_error(1, "header", f"Unknown columns: {', '.join(unknown)}"))
    if "title" not in headers:
        errors.append(make_csv_error(1, "title", "The title column is required"))
    return errors


def csv_row_is_blank(values: list[str]) -> bool:
    return not any(value.strip() for value in values)


def map_csv_row(
    headers: list[str], values: list[str], row_number: int
) -> tuple[CsvRow, list[CsvError]]:
    if len(values) > len(headers):
        return {}, [make_csv_error(row_number, "row", "The row has more values than headers")]
    padded_values = values + [""] * (len(headers) - len(values))
    return dict(zip(headers, padded_values, strict=True)), []


def normalize_title(value: str) -> str:
    return value.strip()


def normalize_description(value: str) -> str:
    return value.strip()


def normalize_status(value: str) -> str:
    return value.strip().lower() or "todo"


def normalize_priority(value: str) -> str:
    return value.strip().lower() or "medium"


def validate_required_title(value: str, row_number: int) -> list[CsvError]:
    if not value:
        return [make_csv_error(row_number, "title", "Title is required")]
    if len(value) > 160:
        return [make_csv_error(row_number, "title", "Title cannot exceed 160 characters")]
    return []


def validate_description_length(value: str, row_number: int) -> list[CsvError]:
    if len(value) > 5000:
        return [
            make_csv_error(row_number, "description", "Description cannot exceed 5000 characters")
        ]
    return []


def validate_status_value(value: str, row_number: int) -> list[CsvError]:
    if value not in VALID_STATUSES:
        choices = ", ".join(sorted(VALID_STATUSES))
        return [make_csv_error(row_number, "status", f"Status must be one of: {choices}")]
    return []


def validate_priority_value(value: str, row_number: int) -> list[CsvError]:
    if value not in VALID_PRIORITIES:
        choices = ", ".join(sorted(VALID_PRIORITIES))
        return [make_csv_error(row_number, "priority", f"Priority must be one of: {choices}")]
    return []


def validate_no_null_bytes(value: str, field: str, row_number: int) -> list[CsvError]:
    if "\x00" in value:
        return [make_csv_error(row_number, field, "Null bytes are not allowed")]
    return []


def normalize_import_row(row: CsvRow) -> CsvRow:
    return {
        "title": normalize_title(row.get("title", "")),
        "description": normalize_description(row.get("description", "")),
        "status": normalize_status(row.get("status", "")),
        "priority": normalize_priority(row.get("priority", "")),
    }


def validate_import_row(row: CsvRow, row_number: int) -> list[CsvError]:
    errors: list[CsvError] = []
    errors.extend(validate_required_title(row["title"], row_number))
    errors.extend(validate_description_length(row["description"], row_number))
    errors.extend(validate_status_value(row["status"], row_number))
    errors.extend(validate_priority_value(row["priority"], row_number))
    for field, value in row.items():
        errors.extend(validate_no_null_bytes(value, field, row_number))
    return errors


def parse_import_rows(rows: list[list[str]]) -> tuple[list[CsvRow], list[CsvError]]:
    if not rows:
        return [], [make_csv_error(1, "file", "The uploaded CSV is empty")]
    headers = normalize_csv_headers(rows[0])
    header_errors = validate_csv_headers(headers)
    if header_errors:
        return [], header_errors
    data_rows = [
        (number, values)
        for number, values in enumerate(rows[1:], 2)
        if not csv_row_is_blank(values)
    ]
    if not data_rows:
        return [], [make_csv_error(2, "file", "The CSV does not contain any work items")]
    if len(data_rows) > MAX_IMPORT_ROWS:
        return [], [
            make_csv_error(
                MAX_IMPORT_ROWS + 2,
                "file",
                f"The CSV cannot contain more than {MAX_IMPORT_ROWS} work items",
            )
        ]
    parsed: list[CsvRow] = []
    errors: list[CsvError] = []
    for row_number, values in data_rows:
        mapped, mapping_errors = map_csv_row(headers, values, row_number)
        errors.extend(mapping_errors)
        if mapping_errors:
            continue
        normalized = normalize_import_row(mapped)
        row_errors = validate_import_row(normalized, row_number)
        errors.extend(row_errors)
        if not row_errors:
            parsed.append(normalized)
    return parsed, errors


def parse_work_items_csv(contents: bytes) -> tuple[list[CsvRow], list[CsvError]]:
    source, decoding_errors = decode_csv_upload(contents)
    if decoding_errors or source is None:
        return [], decoding_errors
    rows, parsing_errors = read_csv_document(source)
    if parsing_errors:
        return [], parsing_errors
    return parse_import_rows(rows)


def csv_row_to_work_item(row: CsvRow) -> WorkItem:
    return WorkItem(
        title=row["title"],
        description=row["description"],
        status=row["status"],
        priority=row["priority"],
    )


def save_imported_work_items(session: Session, rows: list[CsvRow]) -> list[WorkItem]:
    items = [csv_row_to_work_item(row) for row in rows]
    session.add_all(items)
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    for item in items:
        session.refresh(item)
    return items


def enqueue_import_activities(items: list[WorkItem]) -> None:
    for item in items:
        record_activity.delay(item.id, "Work item imported from CSV")


def import_work_items_csv(
    session: Session, contents: bytes
) -> tuple[list[WorkItem], list[CsvError]]:
    rows, errors = parse_work_items_csv(contents)
    if errors:
        return [], errors
    items = save_imported_work_items(session, rows)
    enqueue_import_activities(items)
    return items, []


def import_result(items: list[WorkItem]) -> dict[str, object]:
    return {"imported": len(items), "ids": [item.id for item in items]}


def csv_download_name() -> str:
    return "queueboard-work-items.csv"
