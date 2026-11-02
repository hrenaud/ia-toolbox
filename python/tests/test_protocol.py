import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from document_worker.protocol import KeptDetection, RequestError, parse_request


def request(operation="list_formats", **fields):
    return {"id": str(uuid4()), "operation": operation, **fields}


# Scripts that monkeypatch the converter have to import markitdown at the top,
# before calling main(). The worker itself imports it lazily, after installing
# its output isolation (see document_worker/main.py), so this forced-early
# import drags the import-time warnings of markitdown's own dependencies out
# ahead of that isolation. That noise belongs to the environment rather than to
# the worker — onnxruntime emits one on any Windows release it does not
# recognise — and it would otherwise fail the `stderr == ""` assertions below,
# which exist to catch output the worker lets escape, not output it never saw.
QUIET_MARKITDOWN_IMPORT = """
import warnings
with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    from markitdown import MarkItDown
"""


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
    # Check that formats event has the correct structure and includes .txt
    assert events[0]["id"] == formats["id"]
    assert events[0]["event"] == "formats"
    assert isinstance(events[0]["items"], list)
    assert len(events[0]["items"]) > 0
    txt_format = next(
        (fmt for fmt in events[0]["items"] if fmt["extension"] == ".txt"), None
    )
    assert txt_format is not None
    assert txt_format["label"] == "Text"
    assert txt_format["requires_optional_component"] is False

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
    # Conversion request generates: progress 0, then error result
    assert events[0]["id"] == missing["id"]
    assert events[0]["event"] == "progress"
    assert events[1]["id"] == missing["id"]
    assert events[1]["error_code"] == "input_not_found"
    assert events[1]["status"] == "error"
    # List formats request comes after
    assert any(event["id"] == valid["id"] for event in events[2:])


@pytest.mark.parametrize("failure", ["output_missing", "unsupported"])
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
        }[failure]
    )
    assert "private original" not in json.dumps(event)
    assert source.read_text() == "private original"
    assert output.read_text() == "existing output"


class TestAnonymizationRequests:
    """
    Request validation for the two anonymization operations.

    Checked in process rather than through the worker: these are decisions
    ``parse_request`` makes before anything is read, and a subprocess per case
    would pay for two spaCy models to prove a dictionary key is missing.

    The rule is the one the paths already follow — anything that is not exactly
    right is ``invalid_request``, never a traceback — applied to a payload whose
    offsets will be used to rewrite a document.
    """

    def accepted(self, operation, **fields):
        return parse_request(json.dumps(request(operation, **fields)))

    def refused(self, operation, **fields):
        with pytest.raises(RequestError) as failure:
            self.accepted(operation, **fields)
        return failure.value.code

    def test_the_anonymization_catalog_needs_no_path(self):
        parsed = self.accepted("list_anonymization_formats")

        assert parsed.input_path is None
        assert parsed.output_directory is None

    def test_analyze_has_an_input_and_no_output_folder(self):
        """Analysis writes nothing, so demanding an output folder is a lie."""
        parsed = self.accepted("analyze", input_path="/tmp/dossier.txt")

        assert parsed.input_path == Path("/tmp/dossier.txt")
        assert parsed.output_directory is None

    def test_analyze_still_needs_its_input(self):
        assert self.refused("analyze") == "invalid_path"

    def test_anonymize_carries_paths_payload_and_choices(self):
        parsed = self.accepted(
            "anonymize",
            input_path="/tmp/dossier.txt",
            output_directory="/tmp",
            operator="mask",
            language="en",
            detections=[
                {"unit_id": "content", "start": 3, "end": 17, "entity_type": "PERSON"}
            ],
        )

        assert parsed.operator == "mask"
        assert parsed.language == "en"
        assert parsed.detections == (KeptDetection("content", 3, 17, "PERSON"),)

    def test_the_defaults_are_replace_in_french(self):
        """Replace is the recommended operator, and this is a French product."""
        parsed = self.accepted(
            "anonymize",
            input_path="/tmp/dossier.txt",
            output_directory="/tmp",
            detections=[],
        )

        assert (parsed.operator, parsed.language) == ("replace", "fr")

    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"detections": "content"},
            {"detections": [[]]},
            {"detections": [{"unit_id": "content", "start": 0, "end": 4}]},
            {"detections": [{"unit_id": 7, "start": 0, "end": 4, "entity_type": "X"}]},
            {"detections": [{"unit_id": "", "start": 0, "end": 4, "entity_type": "X"}]},
            {
                "detections": [
                    {"unit_id": "c", "start": -1, "end": 4, "entity_type": "X"}
                ]
            },
            {
                "detections": [
                    {"unit_id": "c", "start": 4, "end": 4, "entity_type": "X"}
                ]
            },
            {
                "detections": [
                    {"unit_id": "c", "start": 5, "end": 4, "entity_type": "X"}
                ]
            },
            {
                "detections": [
                    {"unit_id": "c", "start": 0.5, "end": 4, "entity_type": "X"}
                ]
            },
            {
                "detections": [
                    {"unit_id": "c", "start": True, "end": 4, "entity_type": "X"}
                ]
            },
            {"detections": [{"unit_id": "c", "start": 0, "end": 4, "entity_type": ""}]},
            {"detections": [], "operator": "encrypt"},
            {"detections": [], "operator": None},
            {"detections": [], "language": "de"},
        ],
    )
    def test_a_payload_that_is_not_exactly_right_is_refused(self, payload):
        code = self.refused(
            "anonymize",
            input_path="/tmp/dossier.txt",
            output_directory="/tmp",
            **payload,
        )

        assert code == "invalid_request"

    def test_a_refusal_carries_the_request_id_and_nothing_else(self):
        """The UI needs to know which request failed; it needs no echo of it."""
        item = request(
            "anonymize",
            input_path="/tmp/dossier.txt",
            output_directory="/tmp",
            detections=[{"unit_id": "secret-unit", "start": 0, "end": 4}],
        )

        with pytest.raises(RequestError) as failure:
            parse_request(json.dumps(item))

        assert failure.value.request_id == item["id"]
        assert "secret-unit" not in failure.value.message


def test_the_anonymization_catalog_is_its_own_list():
    """
    Announcing a format the anonymizer cannot rewrite is the worst failure here.

    The two workflows' catalogs are independent: PDF converts to Markdown and
    cannot be rewritten in place, so it must be absent from this one.
    """
    item = request("list_anonymization_formats")

    event = messages(item)[-1]

    assert event["event"] == "formats"
    extensions = [entry["extension"] for entry in event["items"]]
    assert ".docx" in extensions
    assert ".pdf" not in extensions


def test_analyze_then_anonymize_is_one_round_trip_each(tmp_path):
    """The worker keeps no state between the two: the second request carries it."""
    source = tmp_path / "dossier.txt"
    source.write_text("Transmis à Marie Lefebvre.\n", encoding="utf-8")

    analysis = request("analyze", input_path=str(source))
    first = messages(analysis)[-1]
    assert first["status"] == "success", first
    assert first["notes"] == []
    assert [unit["location"] for unit in first["units"]] == ["document"]
    found = next(
        item for item in first["detections"] if item["text"] == "Marie Lefebvre"
    )
    assert found["entity_type"] == "PERSON"
    assert 0 < found["score"] <= 1

    anonymization = request(
        "anonymize",
        input_path=str(source),
        output_directory=str(tmp_path),
        detections=[
            {
                "unit_id": found["unit_id"],
                "start": found["start"],
                "end": found["end"],
                "entity_type": found["entity_type"],
            }
        ],
    )
    second = messages(anonymization)[-1]
    assert second["status"] == "success", second
    assert second["output_path"] == str(tmp_path / "dossier-anonymise.txt")
    assert (
        Path(second["output_path"]).read_text(encoding="utf-8")
        == "Transmis à [PERSONNE 1].\n"
    )
    assert source.read_text(encoding="utf-8") == "Transmis à Marie Lefebvre.\n"


def test_a_document_the_anonymizer_cannot_rewrite_is_refused(tmp_path):
    """A PDF converts and cannot be anonymized, and the worker says so."""
    source = tmp_path / "report.pdf"
    source.write_bytes(b"%PDF-1.4\n")

    event = messages(request("analyze", input_path=str(source)))[-1]

    assert event["status"] == "error"
    assert event["error_code"] == "unsupported_format"


def test_output_filename_is_numbered_when_occupied(tmp_path):
    """When <stem>.md exists, create <stem> (2).md instead of erroring."""
    source = tmp_path / "source.txt"
    source.write_text("new content")
    existing = tmp_path / "source.md"
    existing.write_text("existing output")

    item = request("convert", input_path=str(source), output_directory=str(tmp_path))
    event = messages(item)[-1]

    # Should succeed, not error
    assert event["status"] == "success"
    # Should use numbered name
    assert (tmp_path / "source (2).md").exists()
    assert (tmp_path / "source (2).md").read_text() == "new content"
    # Existing file should be untouched
    assert existing.read_text() == "existing output"
    # Source should be untouched
    assert source.read_text() == "new content"


@pytest.mark.parametrize("fails", [False, True])
def test_converter_diagnostics_and_exceptions_never_leak(tmp_path, fails):
    source = tmp_path / "source.txt"
    source.write_text("private document")
    conversion = request(
        "convert", input_path=str(source), output_directory=str(tmp_path)
    )
    discovery = request()
    process = run_worker(
        [json.dumps(conversion), json.dumps(discovery)],
        script=f"fails = {fails!r}\n"
        + QUIET_MARKITDOWN_IMPORT
        + r"""
import os
import sys
from types import SimpleNamespace
from document_worker.main import main
def fail(*args, **kwargs):
    print('private document')
    print('private document', file=sys.stderr)
    os.write(1, b'NATIVE_STDOUT_SECRET\n')
    os.write(2, b'NATIVE_STDERR_SECRET\n')
    if fails:
        raise RuntimeError('private document')
    return SimpleNamespace(text_content='converted')
MarkItDown.convert_local = fail
main()
os.write(1, b'{"restored":true}\n')
os.write(2, b'descriptors restored\n')
""",
    )
    assert process.returncode == 0
    assert "NATIVE_STDOUT_SECRET" not in process.stdout + process.stderr
    assert "NATIVE_STDERR_SECRET" not in process.stdout + process.stderr
    assert process.stderr == ""
    assert "private document" not in process.stdout
    assert "Traceback" not in process.stdout
    events = [json.loads(line) for line in process.stdout.splitlines()]
    assert events[-2]["id"] == conversion["id"]
    assert events[-2]["status"] == ("error" if fails else "success")
    if fails:
        assert events[-2]["error_code"] == "processing_failed"
    assert events[-1]["id"] == discovery["id"]
    assert (tmp_path / "source.md").exists() is not fails


def test_protocol_handle_remains_writable_while_descriptors_are_redirected():
    discovery = request()
    process = run_worker(
        [json.dumps(discovery)],
        script="""
import document_worker.main as worker
original = worker.process_request
def redirected(request):
    print('ordinary output must be suppressed')
    yield from original(request)
worker.process_request = redirected
worker.main()
""",
    )
    assert process.returncode == 0
    assert process.stderr == ""
    event = json.loads(process.stdout)
    assert event["id"] == discovery["id"]
    assert event["event"] == "formats"


@pytest.mark.parametrize("fails", [False, True])
def test_buffered_libc_output_cannot_escape_after_conversion(tmp_path, fails):
    source = tmp_path / "source.txt"
    source.write_text("text")
    conversion = request(
        "convert", input_path=str(source), output_directory=str(tmp_path)
    )
    process = run_worker(
        [json.dumps(conversion)],
        script=f"fails = {fails!r}\n"
        + QUIET_MARKITDOWN_IMPORT
        + r"""
import ctypes
import os
from types import SimpleNamespace
from document_worker.main import main
libc = ctypes.CDLL('ucrtbase' if os.name == 'nt' else None)
# puts rather than printf: the Windows C runtime defines printf inline in its
# headers and exports no such symbol, so ucrtbase.printf does not exist. puts
# is a real export on both platforms and buffers the same way, which is what
# this test is actually about.
libc.puts.argtypes = [ctypes.c_char_p]
libc.fflush.argtypes = [ctypes.c_void_p]
def convert(*args, **kwargs):
    libc.puts(b'BUFFERED_LIBC_SECRET')
    if fails:
        raise RuntimeError('private error')
    return SimpleNamespace(text_content='converted')
MarkItDown.convert_local = convert
main()
libc.fflush(None)
os.write(1, b'LATE_STDOUT_SECRET')
os.write(2, b'LATE_STDERR_SECRET')
""",
    )
    assert process.returncode == 0
    assert "BUFFERED_LIBC_SECRET" not in process.stdout
    assert process.stderr == ""
    assert "SECRET" not in process.stdout
    events = [json.loads(line) for line in process.stdout.splitlines()]
    assert all(event["id"] == conversion["id"] for event in events)
    assert events[-1]["status"] == ("error" if fails else "success")


@pytest.mark.skipif(sys.platform != "win32", reason="Requires Windows standard handles")
def test_windows_native_standard_handles_are_permanently_silenced():
    discovery = request()
    process = run_worker(
        [json.dumps(discovery)],
        script=r"""
import ctypes
from ctypes import wintypes
from document_worker.main import main
main()
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.GetStdHandle.argtypes = [wintypes.DWORD]
kernel32.GetStdHandle.restype = wintypes.HANDLE
kernel32.WriteFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                              ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
kernel32.WriteFile.restype = wintypes.BOOL
for identifier in (-11, -12):
    data = ctypes.create_string_buffer(b'WIN32_NATIVE_SECRET')
    written = wintypes.DWORD()
    if not kernel32.WriteFile(kernel32.GetStdHandle(identifier), data,
                              len(data.value), ctypes.byref(written), None):
        raise SystemExit(1)
""",
    )
    assert process.returncode == 0
    assert process.stderr == ""
    assert json.loads(process.stdout)["id"] == discovery["id"]
