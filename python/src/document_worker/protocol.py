"""JSON-lines boundary. Never include request data or exception text in errors."""

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

# Which paths each operation requires. Validation is per operation because
# `analyze` writes nothing: demanding an output folder for it would be a lie
# about what the worker is going to do.
_OPERATIONS: dict[str, tuple[str, ...]] = {
    "list_formats": (),
    "list_anonymization_formats": (),
    "convert": ("input_path", "output_directory"),
    "analyze": ("input_path",),
    "anonymize": ("input_path", "output_directory"),
}

_OPERATORS = ("replace", "mask")
_LANGUAGES = ("fr", "en")

_INVALID_PAYLOAD = (
    "The selected items do not match this document. Analyze it again, then retry."
)


class RequestError(ValueError):
    def __init__(self, code: str, message: str, request_id: str | None = None):
        self.code = code
        self.message = message
        self.request_id = request_id


@dataclass(frozen=True)
class KeptDetection:
    """
    One detection the user kept, in the offset space of its own unit.

    Carries no text and no score: both come from the document when it is read
    again, so a request cannot assert what a span contains.
    """

    unit_id: str
    start: int
    end: int
    entity_type: str


@dataclass(frozen=True)
class Request:
    id: str
    operation: str
    input_path: Path | None = None
    output_directory: Path | None = None
    operator: str = "replace"
    language: str = "fr"
    detections: tuple[KeptDetection, ...] = ()


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
    if operation not in _OPERATIONS:
        raise RequestError(
            "unknown_operation", "Choose a supported operation.", request_id
        )
    paths = {name: _path(data, name, request_id) for name in _OPERATIONS[operation]}
    if operation != "anonymize":
        return Request(request_id, operation, **paths)
    return Request(
        request_id,
        operation,
        **paths,
        operator=_choice(data, "operator", _OPERATORS, request_id),
        language=_choice(data, "language", _LANGUAGES, request_id),
        detections=_kept_detections(data, request_id),
    )


def _path(data: dict, name: str, request_id: str) -> Path:
    value = data.get(name)
    if not isinstance(value, str) or "\0" in value or not Path(value).is_absolute():
        raise RequestError(
            "invalid_path",
            "Select an absolute local file and output folder.",
            request_id,
        )
    return Path(value)


def _choice(data: dict, name: str, allowed: tuple[str, ...], request_id: str) -> str:
    """Read an optional choice, defaulting to the first allowed value."""
    value = data.get(name, allowed[0])
    if value not in allowed:
        raise RequestError("invalid_request", _INVALID_PAYLOAD, request_id)
    return value


def _kept_detections(data: dict, request_id: str) -> tuple[KeptDetection, ...]:
    """
    Validate the subset of detections the user kept.

    These offsets are about to rewrite a document, so they are checked as
    strictly as the paths are: the right types, in range, and nothing else.
    Whether they still fit the document is decided when it is read again — here
    only the shape is knowable.
    """
    items = data.get("detections")
    if not isinstance(items, list):
        raise RequestError("invalid_request", _INVALID_PAYLOAD, request_id)

    kept = []
    for item in items:
        if not isinstance(item, dict):
            raise RequestError("invalid_request", _INVALID_PAYLOAD, request_id)
        unit_id, entity_type = item.get("unit_id"), item.get("entity_type")
        start, end = item.get("start"), item.get("end")
        # bool is an int in Python, and True would read as offset 1.
        if (
            not isinstance(unit_id, str)
            or not unit_id
            or not isinstance(entity_type, str)
            or not entity_type
            or isinstance(start, bool)
            or isinstance(end, bool)
            or not isinstance(start, int)
            or not isinstance(end, int)
            or start < 0
            or end <= start
        ):
            raise RequestError("invalid_request", _INVALID_PAYLOAD, request_id)
        kept.append(KeptDetection(unit_id, start, end, entity_type))
    return tuple(kept)


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
