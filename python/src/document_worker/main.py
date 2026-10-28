"""Sequential local worker. The initial boundary enables only plain text."""

import os
import sys
from contextlib import redirect_stderr, redirect_stdout

from document_worker.protocol import (
    RequestError,
    error_result,
    parse_request,
    serialize,
)


def process_request(request):
    if request.operation == "list_formats":
        yield {
            "id": request.id,
            "event": "formats",
            "items": [
                {
                    "extension": ".txt",
                    "label": "Text",
                    "requires_optional_component": False,
                }
            ],
        }
        return
    source, directory = request.input_path, request.output_directory
    if not source.is_file():
        yield error_result(
            request.id, "input_not_found", "Select an existing readable file."
        )
        return
    if not directory.is_dir():
        yield error_result(
            request.id, "invalid_output_directory", "Select an existing output folder."
        )
        return
    if source.suffix.lower() != ".txt":
        yield error_result(
            request.id, "unsupported_format", "Choose a supported file format."
        )
        return
    yield {"id": request.id, "event": "progress", "percent": 0}
    # Third-party output can contain sensitive data. Discard it, including on failure.
    with open(os.devnull, "w") as quiet, redirect_stdout(quiet), redirect_stderr(quiet):
        from markitdown import MarkItDown
        from markitdown.converters import PlainTextConverter

        converter = MarkItDown(enable_builtins=False, enable_plugins=False)
        converter.register_converter(PlainTextConverter())
        text = converter.convert_local(source).text_content
    output = directory / f"{source.stem}.md"
    try:
        stream = output.open("x", encoding="utf-8")
    except FileExistsError:
        yield error_result(
            request.id,
            "output_exists",
            "Choose a folder without an existing output file.",
        )
        return
    try:
        with stream:
            stream.write(text)
    except OSError:
        output.unlink(missing_ok=True)
        raise
    yield {"id": request.id, "event": "progress", "percent": 100}
    yield {
        "id": request.id,
        "event": "result",
        "status": "success",
        "output_path": str(output),
    }


def main():
    # UTF-8 is fixed on both Windows and macOS, independent of the system locale.
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    for line in sys.stdin:
        request_id = None
        try:
            request = parse_request(line)
            request_id = request.id
            for message in process_request(request):
                sys.stdout.write(serialize(message))
                sys.stdout.flush()
        except RequestError as error:
            sys.stdout.write(
                serialize(error_result(error.request_id, error.code, error.message))
            )
        except Exception:  # noqa: BLE001 - isolate each file and never expose library exceptions
            sys.stdout.write(
                serialize(
                    error_result(
                        request_id,
                        "processing_failed",
                        "Could not process this file. Check file and folder access, then retry.",
                    )
                )
            )
        sys.stdout.flush()


if __name__ == "__main__":
    main()
