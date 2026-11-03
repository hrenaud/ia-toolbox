"""Sequential local worker. The initial boundary enables only plain text."""

import os
import sys

from document_worker.protocol import (
    RequestError,
    error_result,
    parse_request,
    serialize,
)


def silence_process_output():
    """Keep ordinary output disconnected from protocol pipes until process exit."""
    # Never restore these descriptors: native libraries may flush buffers much later.
    with open(os.devnull, "w") as quiet:
        os.dup2(quiet.fileno(), 1)
        os.dup2(quiet.fileno(), 2)
    if os.name == "nt":
        # Windows native libraries can use Win32 standard handles instead of CRT FDs.
        import ctypes
        import msvcrt
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.SetStdHandle.argtypes = [wintypes.DWORD, wintypes.HANDLE]
        kernel32.SetStdHandle.restype = wintypes.BOOL
        for identifier, descriptor in ((-11, 1), (-12, 2)):
            if not kernel32.SetStdHandle(identifier, msvcrt.get_osfhandle(descriptor)):
                raise OSError("Could not isolate worker output.")
    sys.stdout = os.fdopen(os.dup(1), "w", encoding="utf-8")
    sys.stderr = os.fdopen(os.dup(2), "w", encoding="utf-8")


def process_request(request):
    if request.operation == "list_formats":
        from document_worker.formats import supported_input_formats

        items = [
            {
                "extension": fmt.extension,
                "label": fmt.label,
                "requires_optional_component": fmt.requires_optional_component,
            }
            for fmt in supported_input_formats()
        ]
        yield {
            "id": request.id,
            "event": "formats",
            "items": items,
        }
        return
    if request.operation == "list_anonymization_formats":
        # A separate catalog on purpose: a format that converts to Markdown is
        # not necessarily one we can rewrite in place.
        from document_worker.anonymization.formats import (
            supported_anonymization_formats,
        )

        yield {
            "id": request.id,
            "event": "formats",
            "items": [
                {"extension": fmt.extension, "label": fmt.label}
                for fmt in supported_anonymization_formats()
            ],
        }
        return
    if request.operation in ("analyze", "anonymize"):
        yield from process_anonymization(request)
        return
    source, directory = request.input_path, request.output_directory
    yield {"id": request.id, "event": "progress", "percent": 0}
    # Output isolation is installed before importing any conversion libraries.
    from document_worker.conversion import convert_file

    result = convert_file(source, directory)
    if result.status == "error":
        yield error_result(request.id, result.error_code, result.message)
        return
    yield {"id": request.id, "event": "progress", "percent": 100}
    yield {
        "id": request.id,
        "event": "result",
        "status": "success",
        "output_path": result.output_path,
    }


def process_anonymization(request):
    """Run one analysis or one anonymization, reporting progress around it."""
    yield {"id": request.id, "event": "progress", "percent": 0}
    # Output isolation is installed before importing detection: loading the
    # language models writes to the real stdout and stderr.
    from document_worker.anonymization import pipeline
    from document_worker.anonymization.model import AdapterError

    try:
        if request.operation == "analyze":
            analysis = pipeline.analyze_file(
                request.input_path, language=request.language
            )
            payload = {
                "language": analysis.language,
                "units": [
                    {
                        "id": unit.id,
                        "location": unit.location,
                        "rewritable": unit.rewritable,
                    }
                    for unit in analysis.units
                ],
                "detections": [
                    {
                        "unit_id": found.unit_id,
                        "start": found.start,
                        "end": found.end,
                        "entity_type": found.entity_type,
                        "score": found.score,
                        "text": found.text,
                        "likely": found.likely,
                        "excerpt": found.excerpt,
                    }
                    for found in analysis.detections
                ],
                "notes": list(analysis.notes),
            }
        else:
            written = pipeline.anonymize_file(
                request.input_path,
                request.output_directory,
                request.detections,
                operator=request.operator,
                language=request.language,
            )
            payload = {
                "output_path": str(written.output_path),
                "notes": list(written.notes),
            }
    except AdapterError as error:
        yield error_result(request.id, error.code, error.message)
        return

    yield {"id": request.id, "event": "progress", "percent": 100}
    yield {"id": request.id, "event": "result", "status": "success", **payload}


def main():
    # UTF-8 is fixed on both Windows and macOS, independent of the system locale.
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    # This duplicated handle stays attached to the protocol pipe during redirection.
    with os.fdopen(os.dup(1), "w", encoding="utf-8") as protocol:
        silence_process_output()
        run_protocol(protocol)


def run_protocol(protocol):
    for line in sys.stdin:
        request_id = None
        try:
            request = parse_request(line)
            request_id = request.id
            for message in process_request(request):
                protocol.write(serialize(message))
                protocol.flush()
        except RequestError as error:
            protocol.write(
                serialize(error_result(error.request_id, error.code, error.message))
            )
        except Exception:  # noqa: BLE001 - isolate each file and never expose library exceptions
            protocol.write(
                serialize(
                    error_result(
                        request_id,
                        "processing_failed",
                        "Could not process this file. Check file and folder access, then retry.",
                    )
                )
            )
        protocol.flush()


if __name__ == "__main__":
    main()
