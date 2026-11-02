"""
Adapters for formats whose text is the file itself.

Four families: plain text, delimited text, JSON, and markup. They share one
preoccupation that has nothing to do with personal data — the round trip. An
anonymizer that re-encodes a file, flips its line endings, or reorders its keys
has damaged a document the user still has to work with, and that damage is
indistinguishable from a bug in the part that matters. So each adapter reuses
what it found: the encoding, the delimiter, the line terminator.
"""

import csv
import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from document_worker.anonymization.adapter import DocumentAdapter, MappedUnit
from document_worker.anonymization.model import AdapterError
from document_worker.anonymization.textmap import TextMap

# Tried in order. utf-8-sig also decodes BOM-less UTF-8, so the BOM is detected
# from the raw bytes rather than from which codec succeeded.
_ENCODINGS = ("utf-8", "cp1252")

# A text document does not contain these. Finding one means the file is binary,
# or text in an encoding we guessed wrong, and either way rewriting it by
# character offset would corrupt it.
_FORBIDDEN_CONTROLS = {chr(code) for code in range(32)} - {"\t", "\n", "\r", "\f"}

# HTML elements that do not break a line of prose. Text around them is one
# string to the detector: "Cher <b>Jean</b> Dupont" is one name, and a detector
# handed the three fragments separately finds none of it.
_HTML_INLINE_TAGS = frozenset(
    [
        "a",
        "abbr",
        "b",
        "bdi",
        "bdo",
        "br",
        "cite",
        "code",
        "data",
        "dfn",
        "em",
        "i",
        "kbd",
        "mark",
        "q",
        "s",
        "samp",
        "small",
        "span",
        "strong",
        "sub",
        "sup",
        "time",
        "u",
        "var",
        "wbr",
    ]
)

# Attributes whose value is shown to a reader, so may name someone.
_VISIBLE_ATTRIBUTES = ("alt", "title", "placeholder", "aria-label", "label", "summary")

_UNANALYZED_TAGS = frozenset({"script", "style"})


@dataclass
class _Document:
    """What an adapter read, kept for the write that may follow."""

    units: list[MappedUnit] = field(default_factory=list)
    notes: tuple[str, ...] = ()
    encoding: str = "utf-8"
    payload: Any = None


def adapter_for(extension: str) -> DocumentAdapter:
    """Return the adapter handling ``extension`` (dotted and lowercase)."""
    if extension in (".csv", ".tsv"):
        return _DelimitedAdapter("\t" if extension == ".tsv" else ",")
    if extension in (".json", ".jsonl"):
        return _JsonAdapter(lines=extension == ".jsonl")
    if extension in (".xml",):
        return _MarkupAdapter(html=False)
    if extension in (".html", ".htm"):
        return _MarkupAdapter(html=True)
    return _PlainTextAdapter()


def _decode(path: Path) -> tuple[str, str]:
    """
    Return the file's text and the encoding to write it back with.

    Raises:
        AdapterError: The bytes are not text we can rewrite safely.
    """
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig"), "utf-8-sig"

    for encoding in _ENCODINGS:
        try:
            text = raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
        if _FORBIDDEN_CONTROLS.isdisjoint(text):
            return text, encoding

    raise AdapterError("unreadable_text", "This file is not readable text.")


def _line_terminator(text: str) -> str:
    """Reuse the file's own line ending, so a copy is not a diff on every line."""
    return "\r\n" if "\r\n" in text else "\n"


class _PlainTextAdapter(DocumentAdapter):
    """Text and Markdown: the whole file is one string, analyzed as it is.

    Markdown is not parsed. Its syntax characters are part of the text a
    detector sees, which costs nothing, and not parsing means not re-rendering.
    """

    UNIT_ID = "content"

    def _load(self, path: Path) -> _Document:
        text, encoding = _decode(path)
        return _Document(
            units=[
                MappedUnit(
                    self.UNIT_ID,
                    TextMap.build([(self.UNIT_ID, text)]),
                    "document",
                )
            ],
            encoding=encoding,
        )

    def _write(
        self, document: _Document, replacements: dict[Any, str], output_path: Path
    ) -> None:
        text = replacements.get(self.UNIT_ID, document.units[0].text_map.text)
        output_path.write_bytes(text.encode(document.encoding))


class _DelimitedAdapter(DocumentAdapter):
    """CSV and TSV: one unit per column.

    A column holds one kind of value and has a name, which is the single most
    useful piece of context a detector can get — a column called "courriel"
    lifts recall far above what its values alone give. One unit per cell would
    give the same context at the cost of one model call per cell.
    """

    def __init__(self, delimiter: str):
        self._delimiter = delimiter

    def _load(self, path: Path) -> _Document:
        text, encoding = _decode(path)
        rows = list(
            csv.reader(io.StringIO(text, newline=""), delimiter=self._delimiter)
        )
        header = rows[0] if rows else []

        units = []
        for column, name in enumerate(header):
            pieces: list[tuple[Any, str]] = []
            for index, row in enumerate(rows[1:], start=1):
                if pieces:
                    pieces.append((None, "\n"))
                pieces.append(
                    ((index, column), row[column] if column < len(row) else "")
                )
            units.append(
                MappedUnit(
                    f"column-{column}",
                    TextMap.build(pieces),
                    f"column:{name}" if name else f"column_number:{column + 1}",
                    context=(name,) if name else (),
                )
            )

        return _Document(
            units=units,
            encoding=encoding,
            payload=(rows, _line_terminator(text)),
        )

    def _write(
        self, document: _Document, replacements: dict[Any, str], output_path: Path
    ) -> None:
        rows, terminator = document.payload
        for (row, column), value in replacements.items():
            rows[row][column] = value

        buffer = io.StringIO(newline="")
        writer = csv.writer(
            buffer,
            delimiter=self._delimiter,
            lineterminator=terminator,
            quoting=csv.QUOTE_MINIMAL,
        )
        writer.writerows(rows)
        output_path.write_bytes(buffer.getvalue().encode(document.encoding))


class _JsonAdapter(DocumentAdapter):
    """JSON and JSON Lines: every string value, with its keys as context.

    Keys are schema rather than content: rewriting one would break whatever
    reads the file, so they are never touched. Numbers and booleans are left
    alone too — a detector asked to find a name in ``42`` can only be wrong.
    """

    def __init__(self, lines: bool):
        self._lines = lines

    def _load(self, path: Path) -> _Document:
        text, encoding = _decode(path)
        documents = self._parse(text)

        units = []
        for index, (line, parsed) in enumerate(documents):
            pieces: list[tuple[Any, str]] = []
            keys: list[str] = []
            for route, value in _walk_strings(parsed):
                if pieces:
                    pieces.append((None, "\n"))
                pieces.append(((index, route), value))
                keys.extend(step for step in route if isinstance(step, str))
            units.append(
                MappedUnit(
                    f"document-{index}",
                    TextMap.build(pieces),
                    f"line:{line + 1}" if self._lines else "document",
                    context=tuple(dict.fromkeys(keys)),
                )
            )

        return _Document(
            units=units,
            encoding=encoding,
            payload=([parsed for _, parsed in documents], _line_terminator(text)),
        )

    def _parse(self, text: str) -> list[tuple[int, Any]]:
        """Return (line index, parsed value) per document in the file."""
        try:
            if not self._lines:
                return [(0, json.loads(text))]
            return [
                (index, json.loads(line))
                for index, line in enumerate(text.splitlines())
                if line.strip()
            ]
        except json.JSONDecodeError as error:
            raise AdapterError(
                "malformed_json", "This file is not valid JSON."
            ) from error

    def _write(
        self, document: _Document, replacements: dict[Any, str], output_path: Path
    ) -> None:
        parsed, terminator = document.payload
        for (index, route), value in replacements.items():
            _set_at(parsed[index], route, value)

        rendered = [json.dumps(value, ensure_ascii=False) for value in parsed]
        text = terminator.join(rendered) + (terminator if self._lines else "")
        output_path.write_bytes(text.encode(document.encoding))


def _walk_strings(value: Any, route: tuple = ()):
    """Yield (route, string) for every string value, in document order."""
    if isinstance(value, str):
        yield route, value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from _walk_strings(child, route + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_strings(child, route + (index,))


def _set_at(parsed: Any, route: tuple, value: str) -> None:
    """Replace the string at ``route``, leaving the structure as it was."""
    if not route:
        raise ValueError("A whole JSON document cannot be replaced.")
    target = parsed
    for step in route[:-1]:
        target = target[step]
    target[route[-1]] = value


class _MarkupAdapter(DocumentAdapter):
    """XML and HTML: the text nodes, with the tags left exactly as they were.

    Writing back through a parser is the only way to keep a document valid, and
    it is why the copy is not byte-identical to the original even where nothing
    changed: attribute quoting and empty-element syntax are normalised. That is
    a cost worth naming, and far smaller than rewriting markup by offset.
    """

    def __init__(self, html: bool):
        self._html = html

    def _load(self, path: Path) -> _Document:
        from lxml import etree

        raw = path.read_bytes()
        try:
            tree = self._parse(raw)
        except (etree.LxmlError, ValueError) as error:
            raise AdapterError(
                "malformed_markup", "This file is not valid markup."
            ) from error

        pieces: list[tuple[Any, str]] = []
        notes: list[str] = []
        self._collect(tree.getroot(), pieces, notes)

        return _Document(
            units=[MappedUnit("markup", TextMap.build(pieces), "document")],
            notes=tuple(dict.fromkeys(notes)),
            encoding=tree.docinfo.encoding or "utf-8",
            payload=tree,
        )

    def _parse(self, raw: bytes):
        from lxml import etree, html

        if self._html:
            return etree.ElementTree(html.fromstring(raw))
        parser = etree.XMLParser(
            resolve_entities=False, no_network=True, load_dtd=False
        )
        return etree.ElementTree(etree.fromstring(raw, parser=parser))

    def _collect(self, element, pieces: list, notes: list) -> None:
        """Walk the tree in reading order, collecting what may be rewritten."""
        from lxml import etree

        tag = element.tag
        if not isinstance(tag, str):
            # A comment or processing instruction. Its own content is never
            # analyzed, but the text that follows it is part of the flow.
            notes.append("markup_code_not_analyzed")
            self._append_tail(element, pieces)
            return

        if self._html:
            for name in _VISIBLE_ATTRIBUTES:
                if element.get(name):
                    pieces.append(((element, f"@{name}"), element.get(name)))
        elif element.attrib:
            notes.append("xml_attributes_not_analyzed")

        if etree.QName(tag).localname.lower() in _UNANALYZED_TAGS:
            notes.append("markup_code_not_analyzed")
            self._append_tail(element, pieces)
            return

        if self._breaks_text(tag) and pieces:
            pieces.append((None, "\n"))
        pieces.append(((element, "text"), element.text or ""))

        for child in element:
            self._collect(child, pieces, notes)

        self._append_tail(element, pieces)

    def _append_tail(self, element, pieces: list) -> None:
        pieces.append(((element, "tail"), element.tail or ""))

    def _breaks_text(self, tag: str) -> bool:
        from lxml import etree

        if not self._html:
            # XML has no inline elements by convention, so every element is a
            # boundary. Missing a name split across two XML elements is the
            # safer error: the opposite fuses unrelated values into one.
            return True
        return etree.QName(tag).localname.lower() not in _HTML_INLINE_TAGS

    def _write(
        self, document: _Document, replacements: dict[Any, str], output_path: Path
    ) -> None:
        for (element, slot), value in replacements.items():
            if slot.startswith("@"):
                element.set(slot[1:], value)
                continue
            if slot == "text":
                element.text = value
                self._preserve_space(element, value)
            else:
                element.tail = value
                parent = element.getparent()
                if parent is not None:
                    self._preserve_space(parent, value)

        document.payload.write(
            str(output_path),
            encoding=document.encoding,
            xml_declaration=not self._html
            and document.payload.docinfo.xml_version is not None,
            method="html" if self._html else "xml",
        )

    def _preserve_space(self, element, value: str) -> None:
        """
        Keep whitespace an anonymized value needs.

        XML collapses or drops leading and trailing whitespace unless the
        element says to keep it, which would silently glue a replacement to the
        word beside it.
        """
        if self._html or not value or value == value.strip():
            return
        element.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
