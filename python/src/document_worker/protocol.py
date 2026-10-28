"""JSON-lines boundary. Never include request data or exception text in errors."""

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID


class RequestError(ValueError):
    def __init__(self, code: str, message: str, request_id: str | None = None):
        self.code = code
        self.message = message
        self.request_id = request_id


@dataclass(frozen=True)
class Request:
    id: str
    operation: str
    input_path: Path | None = None
    output_directory: Path | None = None


def parse_request(line: str) -> Request:
    try:
        data = json.loads(line)
        if not isinstance(data, dict) or not isinstance(data.get("id"), str):
            raise TypeError
        UUID(data["id"])
    except (ValueError, TypeError, RecursionError):
        raise RequestError(
            "invalid_request", "Send a JSON object with a valid request ID."
        ) from None
    request_id = data["id"]
    operation = data.get("operation")
    if operation not in ("list_formats", "convert"):
        raise RequestError(
            "unknown_operation", "Choose a supported operation.", request_id
        )
    if operation == "list_formats":
        return Request(request_id, operation)
    paths = []
    for name in ("input_path", "output_directory"):
        value = data.get(name)
        if not isinstance(value, str) or "\0" in value or not Path(value).is_absolute():
            raise RequestError(
                "invalid_path",
                "Select an absolute local file and output folder.",
                request_id,
            )
        paths.append(Path(value))
    return Request(request_id, operation, *paths)


def error_result(request_id: str | None, code: str, message: str) -> dict:
    return {
        "id": request_id,
        "event": "result",
        "status": "error",
        "error_code": code,
        "message": message,
    }


def serialize(message: dict) -> str:
    return (
        json.dumps(message, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
        + "\n"
    )
