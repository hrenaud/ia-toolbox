"""
Adapters for the Office packages: DOCX, XLSX, PPTX.

All three are a zip of XML parts, and all three store a line of prose as a
series of runs split wherever the editor felt like splitting it. So all three
share one machine: a list of rules saying which parts hold text, which elements
hold it, and which elements end a line. The format-specific knowledge is in
those rules and nowhere else.

Two commitments hold the copy together. Parts we do not rewrite are copied byte
for byte, including images, themes and the relationship graph — anything else
risks a package Office refuses to open. And text we read but cannot safely
rewrite, such as a formula literal or a sheet name, is shown to the user and
left alone rather than quietly skipped.
"""

import re
import zipfile
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from document_worker.anonymization.adapter import DocumentAdapter, MappedUnit
from document_worker.anonymization.model import AdapterError
from document_worker.anonymization.textmap import TextMap

_WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_DRAWING = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_PRESENTATION = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
_SHEET = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

_PROPERTY_PARTS = ("docProps/core.xml", "docProps/app.xml")


@dataclass(frozen=True)
class _Rule:
    """Which parts hold text, and where in them it is.

    Attributes:
        name: Suffix of the unit id, so two rules over the same part stay
            distinguishable.
        patterns: Part-name globs this rule applies to.
        location: Location code from ``locations.LOCATION_CODES``, with "{n}"
            standing for the number in the part name — which is what the user
            calls the slide or the sheet. The interface translates it.
        text_tags: Elements whose text is a fragment of the unit's string.
        break_tags: Elements that end a line, so two of them cannot fuse into
            one word.
        attributes: (element tag, attribute) pairs holding visible text.
        rewritable: False for text that is reported but never written back.
    """

    name: str
    patterns: tuple[str, ...]
    location: str
    text_tags: tuple[str, ...] = ()
    break_tags: tuple[str, ...] = ()
    attributes: tuple[tuple[str, str], ...] = ()
    rewritable: bool = True


_WORD_TEXT = (f"{_WORD}t",)
_WORD_BREAK = (f"{_WORD}p", f"{_WORD}br", f"{_WORD}tc")

_DOCX_RULES = (
    _Rule("text", ("word/document.xml",), "document_body", _WORD_TEXT, _WORD_BREAK),
    _Rule("text", ("word/header*.xml",), "header:{n}", _WORD_TEXT, _WORD_BREAK),
    _Rule("text", ("word/footer*.xml",), "footer:{n}", _WORD_TEXT, _WORD_BREAK),
    _Rule("text", ("word/footnotes.xml",), "footnotes", _WORD_TEXT, _WORD_BREAK),
    _Rule("text", ("word/endnotes.xml",), "endnotes", _WORD_TEXT, _WORD_BREAK),
    _Rule("text", ("word/comments.xml",), "comments", _WORD_TEXT, _WORD_BREAK),
)

_SLIDE_TEXT = (f"{_DRAWING}t",)
_SLIDE_BREAK = (f"{_DRAWING}p", f"{_DRAWING}br")
# Alt text is read aloud by assistive technology and routinely describes who is
# in a photograph, so it is part of the document's personal data.
_SLIDE_ATTRIBUTES = ((f"{_PRESENTATION}cNvPr", "descr"),)

_PPTX_RULES = (
    _Rule(
        "text",
        ("ppt/slides/slide*.xml",),
        "slide:{n}",
        _SLIDE_TEXT,
        _SLIDE_BREAK,
        _SLIDE_ATTRIBUTES,
    ),
    _Rule(
        "text",
        ("ppt/notesSlides/notesSlide*.xml",),
        "slide_notes:{n}",
        _SLIDE_TEXT,
        _SLIDE_BREAK,
    ),
    _Rule(
        "text",
        ("ppt/slideLayouts/slideLayout*.xml",),
        "slide_layout:{n}",
        _SLIDE_TEXT,
        _SLIDE_BREAK,
    ),
    _Rule(
        "text",
        ("ppt/slideMasters/slideMaster*.xml",),
        "slide_master:{n}",
        _SLIDE_TEXT,
        _SLIDE_BREAK,
    ),
    _Rule(
        "text",
        ("ppt/notesMasters/notesMaster*.xml",),
        "notes_master:{n}",
        _SLIDE_TEXT,
        _SLIDE_BREAK,
    ),
    _Rule("text", ("ppt/comments/*.xml",), "slide_comments", _SLIDE_TEXT, _SLIDE_BREAK),
)

_SHEET_HEADER_TAGS = tuple(
    f"{_SHEET}{position}{part}"
    for position in ("odd", "even", "first")
    for part in ("Header", "Footer")
)
_SHEET_TEXT = (f"{_SHEET}t",) + _SHEET_HEADER_TAGS
_SHEET_BREAK = (f"{_SHEET}si", f"{_SHEET}c") + _SHEET_HEADER_TAGS

_XLSX_RULES = (
    _Rule("text", ("xl/sharedStrings.xml",), "cell_values", _SHEET_TEXT, _SHEET_BREAK),
    _Rule(
        "text", ("xl/worksheets/sheet*.xml",), "sheet:{n}", _SHEET_TEXT, _SHEET_BREAK
    ),
    _Rule("text", ("xl/comments*.xml",), "cell_comments", _SHEET_TEXT, _SHEET_BREAK),
    # A formula is code. Its literals are shown so nothing is hidden, but
    # rewriting one by offset is how a workbook stops opening.
    _Rule(
        "formula",
        ("xl/worksheets/sheet*.xml",),
        "sheet_formulas:{n}",
        (f"{_SHEET}f",),
        (f"{_SHEET}f",),
        rewritable=False,
    ),
    # Renaming a sheet breaks every formula and defined name that refers to it.
    _Rule(
        "sheetname",
        ("xl/workbook.xml",),
        "sheet_names",
        attributes=((f"{_SHEET}sheet", "name"), (f"{_SHEET}definedName", "name")),
        rewritable=False,
    ),
)


def adapter_for(extension: str) -> DocumentAdapter:
    """Return the adapter handling ``extension`` (dotted and lowercase)."""
    if extension == ".pptx":
        return _OoxmlAdapter(_PPTX_RULES, ("ppt/slides/slide*.xml",))
    if extension == ".xlsx":
        return _OoxmlAdapter(
            _XLSX_RULES, ("xl/workbook.xml", "xl/worksheets/sheet*.xml")
        )
    return _OoxmlAdapter(_DOCX_RULES, ("word/document.xml",))


@dataclass
class _Package:
    """A parsed package, kept for the write that may follow."""

    path: Path
    units: list[MappedUnit]
    notes: tuple[str, ...]
    trees: dict[str, Any]


class _OoxmlAdapter(DocumentAdapter):
    """One adapter for all three packages, configured by its rules."""

    def __init__(self, rules: tuple[_Rule, ...], required: tuple[str, ...]):
        self._rules = rules
        self._required = required

    def _load(self, path: Path) -> _Package:
        from lxml import etree

        try:
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
                if not any(_matches(name, self._required) for name in names):
                    raise AdapterError(
                        "unsupported_package",
                        "This file is not a readable Office document.",
                    )
                parts = {
                    name: archive.read(name)
                    for name in names
                    if _matches(name, self._rule_patterns()) or name in _PROPERTY_PARTS
                }
        except zipfile.BadZipFile as error:
            raise AdapterError(
                "unsupported_package", "This file is not a readable Office document."
            ) from error

        parser = etree.XMLParser(
            resolve_entities=False, no_network=True, load_dtd=False
        )
        trees = {}
        for name, raw in parts.items():
            try:
                trees[name] = etree.fromstring(raw, parser=parser)
            except etree.LxmlError as error:
                raise AdapterError(
                    "unsupported_package",
                    "This document contains a part we cannot read.",
                ) from error

        units = []
        for rule in self._rules:
            for name in sorted(name for name in trees if _matches(name, rule.patterns)):
                pieces = self._collect(name, trees[name], rule)
                if not any(key is not None for key, _ in pieces):
                    continue
                units.append(
                    MappedUnit(
                        f"{name}|{rule.name}",
                        TextMap.build(pieces),
                        rule.location.format(n=_number_in(name)),
                        rewritable=rule.rewritable,
                    )
                )

        return _Package(path, units, self._notes(names, trees), trees)

    def _rule_patterns(self) -> tuple[str, ...]:
        return tuple(pattern for rule in self._rules for pattern in rule.patterns)

    def _collect(self, part: str, root, rule: _Rule) -> list[tuple[Any, str]]:
        """Walk the part in reading order, collecting what the rule names.

        Tails are ignored on purpose: in OOXML the whitespace between elements
        is formatting, not content, and treating it as text would both pollute
        the detector's input and shift every offset after it.
        """
        pieces: list[tuple[Any, str]] = []
        for element in root.iter():
            if not isinstance(element.tag, str):
                continue
            for tag, attribute in rule.attributes:
                if element.tag == tag and element.get(attribute):
                    pieces.append(
                        ((part, element, f"@{attribute}"), element.get(attribute))
                    )
            if element.tag in rule.break_tags and pieces:
                pieces.append((None, "\n"))
            if element.tag in rule.text_tags:
                pieces.append(((part, element, "text"), element.text or ""))
        return pieces

    def _notes(self, names: list[str], trees: dict[str, Any]) -> tuple[str, ...]:
        notes = []

        # Deleted and inserted text lives in w:delText, outside the runs we
        # rewrite. A user who later accepts the revisions would otherwise find
        # the personal data back in the document.
        if any(
            element.tag in (f"{_WORD}delText", f"{_WORD}ins")
            for tree in trees.values()
            for element in tree.iter()
            if isinstance(element.tag, str)
        ):
            notes.append("tracked_changes_not_rewritten")

        if any(
            (element.text or "").strip()
            for name in _PROPERTY_PARTS
            if name in trees
            for element in trees[name].iter()
        ):
            notes.append("document_properties_not_rewritten")

        # One shared string can be referenced by any number of cells, so a
        # single replacement changes all of them.
        if "xl/sharedStrings.xml" in names:
            notes.append("xlsx_shared_strings_reused")

        return tuple(notes)

    def _write(
        self, document: _Package, replacements: dict[Any, str], output_path: Path
    ) -> None:
        from lxml import etree

        changed = set()
        for (part, element, slot), value in replacements.items():
            if slot.startswith("@"):
                element.set(slot[1:], value)
            else:
                element.text = value
                if value and value != value.strip():
                    # OOXML drops leading and trailing whitespace unless the
                    # run says to keep it, which would glue a replacement to
                    # the word beside it.
                    element.set(_XML_SPACE, "preserve")
            changed.add(part)

        with (
            zipfile.ZipFile(document.path) as source,
            zipfile.ZipFile(output_path, "w") as target,
        ):
            for info in source.infolist():
                if info.filename in changed:
                    data = etree.tostring(
                        etree.ElementTree(document.trees[info.filename]),
                        xml_declaration=True,
                        encoding="UTF-8",
                        standalone=True,
                    )
                else:
                    data = source.read(info.filename)
                target.writestr(info, data)


def _matches(name: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch(name, pattern) for pattern in patterns)


def _number_in(name: str) -> str:
    """The number a user would use to name this part: slide 7, sheet 2."""
    found = re.findall(r"(\d+)", Path(name).stem)
    return found[-1] if found else ""
