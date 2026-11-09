"""
The values the anonymization pipeline passes between its stages.

The pipeline is one path for every format: extract text units, detect personal
data in them, let the user drop detections, turn the rest into edits, write a
copy. Each format contributes only an adapter that produces units and applies
edits. These types are the whole contract between the two.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TextUnit:
    """
    One independently analyzed string, with its own offset space.

    A unit is a CSV column, a DOCX part, a PPTX slide, an XLSX sheet. Text is
    never concatenated across units, because an offset spanning two of them
    cannot be mapped back to a place in the document.

    Attributes:
        id: Opaque to the pipeline; the adapter's own handle for this unit.
        text: The string a detector analyzes.
        location: Where this text is, in words the user recognises, such as
            "page header" or "slide 4 notes".
        context: Extra words given to the detector as context without being
            part of the text — a CSV header name, a JSON key. A column called
            "courriel" lifts recall far above what its values alone give.
        rewritable: False for text that is read and reported but never written
            back, such as a string literal inside a spreadsheet formula.
        cells: The span of each cell, for a unit that is a column of a table.
            Empty for everything else, which is how a column is recognised.
            Reported rather than derived: a quoted CSV cell may hold the
            newline the cells are joined with, so splitting the text on
            newlines would cut it in two.
    """

    id: str
    text: str
    location: str
    context: tuple[str, ...] = ()
    rewritable: bool = True
    cells: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True)
class Detection:
    """
    One span of personal data found in one unit.

    Attributes:
        likely: False for a detection whose shape is the one the model gets
            wrong most often — a lone capitalised word opening a line. The
            review screen ranks those below the rest instead of dropping them,
            because the same shape is what a one-word name in a table cell
            looks like. ``score`` is the detector's own confidence and answers
            a different question; this one is ours.
        excerpt: The value with a few words either side, on one line, elided
            with "…" where it was cut. "Loire" alone is a question nobody can
            answer; "salle Loire — locaux de" is a room.
        column: True for one cell of a column typed as a whole. The review
            screen collapses every cell of that column into a single row on
            this flag, because the decision is about the column, not the cell.
    """

    unit_id: str
    start: int
    end: int
    entity_type: str
    score: float
    text: str
    likely: bool = True
    excerpt: str = ""
    column: bool = False


@dataclass(frozen=True)
class Edit:
    """One replacement to write back, in a unit's offset space."""

    unit_id: str
    start: int
    end: int
    replacement: str


@dataclass(frozen=True)
class Extraction:
    """
    What an adapter read from a document.

    Attributes:
        units: The strings to analyze.
        notes: Codes for content that is not analyzed or not rewritten, such as
            embedded images or tracked changes. The UI translates them. This
            report is a feature, not a footnote: it is what stops a user
            believing a copy is clean when it is only partly clean.
    """

    units: list[TextUnit] = field(default_factory=list)
    notes: tuple[str, ...] = ()


class AdapterError(Exception):
    """A document the adapter cannot read, with a code the worker can report."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message
