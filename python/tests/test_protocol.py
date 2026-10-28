import json
import subprocess
import sys
from uuid import uuid4

import pytest


def request(operation="list_formats", **fields):
    return {"id": str(uuid4()), "operation": operation, **fields}


def run_worker(lines, script=None):
    return subprocess.run(
        [sys.executable, "-c", script]
        if script
        else [sys.executable, "-m", "document_worker.main"],
        input="".join(line + "\n" for line in lines),
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )


def messages(*requests):
    process = run_worker([json.dumps(item) for item in requests])
    assert process.returncode == 0, process.stderr
    assert process.stderr == ""
    return [json.loads(line) for line in process.stdout.splitlines()]


def test_discovery_and_conversion_have_correlated_protocol_only_output(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("Hello local world.\n", encoding="utf-8")
    formats = request()
    conversion = request(
        "convert", input_path=str(source), output_directory=str(tmp_path)
    )
    events = messages(formats, conversion)
    assert events[0] == {
        "id": formats["id"],
        "event": "formats",
        "items": [
            {"extension": ".txt", "label": "Text", "requires_optional_component": False}
        ],
    }
    assert all(event["id"] == conversion["id"] for event in events[1:])
    assert [event["percent"] for event in events if event["event"] == "progress"] == [
        0,
        100,
    ]
    assert events[-1] == {
        "id": conversion["id"],
        "event": "result",
        "status": "success",
        "output_path": str(tmp_path / "source.md"),
    }
    assert (tmp_path / "source.md").read_text() == "Hello local world.\n"
    assert source.read_text() == "Hello local world.\n"


@pytest.mark.parametrize("line", ["{broken secret", "[]", "null", '{"id":"bad"}'])
def test_malformed_request_is_safe_and_next_request_still_works(line):
    valid = request()
    process = run_worker([line, json.dumps(valid)])
    assert process.returncode == 0
    events = [json.loads(value) for value in process.stdout.splitlines()]
    assert events[0]["status"] == "error"
    assert events[0]["error_code"] == "invalid_request"
    assert events[0]["id"] is None
    assert events[1]["id"] == valid["id"]
    assert "secret" not in process.stdout + process.stderr
    assert "Traceback" not in process.stdout + process.stderr


@pytest.mark.parametrize(
    "operation,fields,code",
    [
        ("sh", {"command": "echo private"}, "unknown_operation"),
        ("convert", {}, "invalid_path"),
        (
            "convert",
            {"input_path": "relative.txt", "output_directory": "/"},
            "invalid_path",
        ),
        ("convert", {"input_path": 42, "output_directory": "/"}, "invalid_path"),
        (
            "convert",
            {"input_path": "/bad\u0000path", "output_directory": "/"},
            "invalid_path",
        ),
    ],
)
def test_invalid_operation_or_paths(operation, fields, code):
    item = request(operation, **fields)
    event = messages(item)[-1]
    assert event["id"] == item["id"]
    assert event["status"] == "error"
    assert event["error_code"] == code


def test_per_file_error_does_not_stop_next_request(tmp_path):
    missing = request(
        "convert",
        input_path=str(tmp_path / "missing.txt"),
        output_directory=str(tmp_path),
    )
    valid = request()
    events = messages(missing, valid)
    assert events[0]["id"] == missing["id"]
    assert events[0]["error_code"] == "input_not_found"
    assert events[0]["status"] == "error"
    assert events[1]["id"] == valid["id"]


@pytest.mark.parametrize("failure", ["output_missing", "unsupported", "occupied"])
def test_structured_file_errors_preserve_existing_files(tmp_path, failure):
    source = tmp_path / ("source.odt" if failure == "unsupported" else "source.txt")
    source.write_text("private original")
    output = tmp_path / "source.md"
    output.write_text("existing output")
    directory = tmp_path / "missing" if failure == "output_missing" else tmp_path
    item = request("convert", input_path=str(source), output_directory=str(directory))
    event = messages(item)[-1]
    assert event["status"] == "error"
    assert (
        event["error_code"]
        == {
            "output_missing": "invalid_output_directory",
            "unsupported": "unsupported_format",
            "occupied": "output_exists",
        }[failure]
    )
    assert "private original" not in json.dumps(event)
    assert source.read_text() == "private original"
    assert output.read_text() == "existing output"


def test_converter_diagnostics_and_exceptions_never_leak(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("private document")
    conversion = request(
        "convert", input_path=str(source), output_directory=str(tmp_path)
    )
    discovery = request()
    process = run_worker(
        [json.dumps(conversion), json.dumps(discovery)],
        script="""
import sys
from markitdown import MarkItDown
from document_worker.main import main
def fail(*args, **kwargs):
    print('private document')
    print('private document', file=sys.stderr)
    raise RuntimeError('private document')
MarkItDown.convert_local = fail
main()
""",
    )
    assert process.returncode == 0
    assert process.stderr == ""
    assert "private document" not in process.stdout
    assert "Traceback" not in process.stdout
    events = [json.loads(line) for line in process.stdout.splitlines()]
    assert events[-2]["id"] == conversion["id"]
    assert events[-2]["error_code"] == "processing_failed"
    assert events[-1]["id"] == discovery["id"]
    assert not (tmp_path / "source.md").exists()
