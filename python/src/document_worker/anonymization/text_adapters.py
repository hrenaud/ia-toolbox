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
import re
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
    if extension in (".md", ".markdown"):
        return _MarkdownAdapter()
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
    """Plain text: the whole file is one string, analyzed as it is."""

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


# A fenced code block, or an HTML comment. Both can span lines, so both are
# found over the whole document before anything is read line by line. Their
# content is analyzed like any other text; only their delimiters are not.
_MARKDOWN_CODE = re.compile(
    r"^[ \t]{0,3}(`{3,}|~{3,})[^\n]*(?:\n|$)"
    r"(?:(?!^[ \t]{0,3}\1)[^\n]*(?:\n|$))*"
    r"(?:^[ \t]{0,3}\1[^\n]*(?:\n|$))?"
    r"|<!--.*?-->",
    re.DOTALL | re.MULTILINE,
)

# What introduces a line rather than belonging to it: blockquote markers, then
# an ATX heading marker or a list bullet.
_MARKDOWN_PREFIX = re.compile(
    r"^[ \t]*(?:>[ \t]*)*(?:#{1,6}[ \t]+|(?:[-*+]|\d{1,9}[.)])[ \t]+)?"
)

# A table's second row: dashes, colons and pipes only.
_MARKDOWN_TABLE_RULE = re.compile(r"^[ \t]*\|?[ \t:|-]*-[ \t:|-]*$")

# Syntax inside a line. Underscores are left alone on purpose: `admin_user` is
# one word to a reader and cutting it would change the text the detector sees
# for no gain, whereas asterisk emphasis is unambiguous.
_MARKDOWN_INLINE = re.compile(r"`+[^`\n]*`+|</?[A-Za-z][^>\n]*>|\*{1,3}|~~")

# Reported by the HTML adapter, whose scripts and styles really are skipped.
# Markdown no longer emits it: it analyzes code and comments like any other text.
_CODE_NOTE = "markup_code_not_analyzed"

# What opens or closes a fenced code block, at the start of its own line.
_MARKDOWN_FENCE = re.compile(r"[ \t]{0,3}(?:`{3,}|~{3,})")


@dataclass(frozen=True)
class _MarkdownPiece:
    """One stretch of a Markdown file, and what may be done with it."""

    text: str
    # Whether the detector sees it and a replacement may be written into it.
    analyzed: bool
    # Whether the detector needs a line break here, for excluded pieces that
    # separate blocks. False for inline syntax, where the prose either side is
    # one sentence.
    boundary: bool = False
    note: str | None = None
    # The TextMap key, assigned only to analyzed pieces.
    key: int | None = None


class _MarkdownAdapter(DocumentAdapter):
    """Markdown: the prose, with the syntax left out of what is analyzed.

    Not parsed into a tree and not re-rendered — the file is split into the
    stretches that carry content and the stretches that carry structure, and
    only the first kind reaches the detector or can be written to.

    Handing the raw file to a model instead, as this adapter first did, wrecks
    the sentences: `**Lieu :** Nantes, salle Loire` yields `salle` as a person
    and a table cell comes back with its closing pipe in the span.

    Content is content wherever it sits. A code block and an HTML comment are
    delimiters around text, and that text holds addresses and names like the
    rest of the file — a review note reading "relire avec Sophie Marchand" is
    exactly what a user anonymizes a document to remove. So their content is
    analyzed and rewritable, and only their delimiters are structure.
    """

    UNIT_ID = "content"

    def _load(self, path: Path) -> _Document:
        text, encoding = _decode(path)

        pieces: list[_MarkdownPiece] = []
        mapped: list[tuple[Any, str]] = []
        notes: list[str] = []
        for piece in _markdown_pieces(text):
            if piece.note:
                notes.append(piece.note)
            if piece.analyzed:
                piece = _MarkdownPiece(
                    piece.text, True, piece.boundary, piece.note, key=len(pieces)
                )
                mapped.append((piece.key, piece.text))
            elif piece.boundary and mapped and mapped[-1][0] is not None:
                # One break between two analyzed stretches, so the last word of
                # a block cannot fuse with the first word of the next.
                mapped.append((None, "\n"))
            pieces.append(piece)

        return _Document(
            units=[
                MappedUnit(self.UNIT_ID, TextMap.build(mapped), "document"),
            ],
            notes=tuple(dict.fromkeys(notes)),
            encoding=encoding,
            payload=pieces,
        )

    def _write(
        self, document: _Document, replacements: dict[Any, str], output_path: Path
    ) -> None:
        rebuilt = "".join(
            piece.text if piece.key is None else replacements.get(piece.key, piece.text)
            for piece in document.payload
        )
        output_path.write_bytes(rebuilt.encode(document.encoding))


def _markdown_pieces(text: str):
    """Yield the file's pieces in order, content and structure alike."""
    for chunk, excluded in _split_on(text, _MARKDOWN_CODE):
        if excluded:
            yield from _markdown_delimited(chunk)
        else:
            yield from _markdown_lines(chunk)


def _markdown_delimited(chunk: str):
    """
    Split a fenced code block or an HTML comment into delimiters and content.

    The content is yielded as one analyzed piece, newlines and all. The detector
    reads a unit one line at a time anyway, and keeping the block whole means a
    replacement lands at its real offset inside the file.
    """
    if chunk.startswith("<!--"):
        yield _MarkdownPiece("<!--", False, boundary=True)
        # The pattern only matches a closed comment, so the end is always there.
        if body := chunk[len("<!--") : -len("-->")]:
            yield _MarkdownPiece(body, True)
        yield _MarkdownPiece("-->", False, boundary=True)
        return

    # The opening fence carries the info string — `python` is not prose.
    opening, *rest = chunk.splitlines(keepends=True)
    yield _MarkdownPiece(opening, False, boundary=True)
    # An unterminated block runs to the end of the file and has no closing line.
    closing = rest.pop() if rest and _MARKDOWN_FENCE.match(rest[-1]) else None
    if rest:
        yield _MarkdownPiece("".join(rest), True)
    if closing:
        yield _MarkdownPiece(closing, False, boundary=True)


def _markdown_lines(chunk: str):
    for line in chunk.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        terminator = line[len(body) :]

        prefix = _MARKDOWN_PREFIX.match(body).group(0)
        if prefix:
            yield _MarkdownPiece(prefix, False, boundary=True)
        rest = body[len(prefix) :]

        if _MARKDOWN_TABLE_RULE.match(rest):
            yield _MarkdownPiece(rest, False, boundary=True)
        elif "|" in rest:
            yield from _markdown_cells(rest)
        else:
            yield from _markdown_inline(rest)

        if terminator:
            yield _MarkdownPiece(terminator, False, boundary=True)


def _markdown_cells(row: str):
    """A pipe is the boundary between two values, never part of one."""
    for cell in re.split(r"(\|)", row):
        if cell == "|":
            yield _MarkdownPiece(cell, False, boundary=True)
        else:
            yield from _markdown_inline(cell)


def _markdown_inline(segment: str):
    for chunk, excluded in _split_on(segment, _MARKDOWN_INLINE):
        if not chunk:
            continue
        if not excluded:
            yield _MarkdownPiece(chunk, True)
        elif chunk.startswith("`"):
            # A code span's backticks are syntax; what they wrap is text.
            ticks = len(chunk) - len(chunk.lstrip("`"))
            body = chunk[ticks:].rstrip("`")
            yield _MarkdownPiece(chunk[:ticks], False)
            if body:
                yield _MarkdownPiece(body, True)
            yield _MarkdownPiece(chunk[ticks + len(body) :], False)
        else:
            yield _MarkdownPiece(chunk, False)


def _split_on(text: str, pattern: re.Pattern):
    """Yield (chunk, matched) covering ``text`` exactly once, in order."""
    position = 0
    for match in pattern.finditer(text):
        if match.start() > position:
            yield text[position : match.start()], False
        yield match.group(0), True
        position = match.end()
    if position < len(text):
        yield text[position:], False


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
            # Where each cell sits in the column's text, tracked as the text is
            # built: a cell may contain the newline the cells are joined with,
            # so the spans cannot be recovered from the finished string.
            cells: list[tuple[int, int]] = []
            offset = 0
            for index, row in enumerate(rows[1:], start=1):
                if pieces:
                    pieces.append((None, "\n"))
                    offset += 1
                value = row[column] if column < len(row) else ""
                cells.append((offset, offset + len(value)))
                pieces.append(((index, column), value))
                offset += len(value)
            units.append(
                MappedUnit(
                    f"column-{column}",
                    TextMap.build(pieces),
                    f"column:{name}" if name else f"column_number:{column + 1}",
                    context=(name,) if name else (),
                    cells=tuple(cells),
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
            # A comment or a processing instruction. A comment is prose — a
            # review note naming someone is exactly what the user is removing —
            # so it is analyzed and rewritable, on its own line since it sits
            # between blocks. A processing instruction carries no prose, and
            # giving it an empty piece costs nothing.
            pieces.append((None, "\n"))
            pieces.append(((element, "text"), element.text or ""))
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
