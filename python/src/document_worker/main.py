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
