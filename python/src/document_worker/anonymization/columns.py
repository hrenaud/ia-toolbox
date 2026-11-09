"""
Typing a column of a table as a whole instead of cell by cell.

A column is not prose. Every cell in it holds the same kind of value, and that
is a stronger claim than anything a detector can make about one cell on its
own. Two things follow, and both are improvements on reading a table as text.

The copy stops leaking. A model that finds a name in six cells of a column and
misses the seventh left that seventh name in the anonymized file, and never
offered it for review — nobody can untick a row that was never shown. When the
column is replaced as a whole, a missed cell is replaced with the rest.

And the review stops repeating itself. A column of eight names was eight rows
asking the same question; it is now one row, with one type to confirm or
correct. Correcting it corrects the whole column, which is the point: the
detector reads "Organisation" as a column of people often enough, and that is
one click rather than seven.

Two measurements decide it, and it takes both. **Fill** is how much of a cell
the detections cover, averaged over the cells where something was found: it
says the cells *are* values rather than sentences containing one. **Reach** is
how many of the cells something was found in at all: it says the column is
made of those values rather than holding one by accident.

Neither alone would do. Fill on its own accepts a column where one cell in
twenty is a name; reach on its own accepts a column of comments that each
mention somebody. And what fill deliberately does not measure is recall — a
column of eight names the model only found six of still fills the six, which is
exactly the case that has to be accepted, since those two missed names are the
leak this is here to close.

The thresholds come from the sample directory. Fill: 0.76 to 1.00 for the
columns of names, organizations, addresses, emails, phone numbers and dates,
against 0.41 for a free-text comment column. Reach: 0.88 to 1.00 against 0.25.
Both thresholds sit in the middle of their gap rather than on either edge.
"""

from collections.abc import Iterable

from document_worker.anonymization.model import Detection, TextUnit

# How much of a cell holding personal data is personal data, averaged over the
# cells where any was found. Below this, the cells are prose.
_FILL = 0.6

# How many of a column's cells hold personal data at all. Below this, the
# column is something else with personal data in a few of its cells.
_REACH = 0.5


def type_columns(
    units: Iterable[TextUnit], detections: Iterable[Detection]
) -> list[Detection]:
    """
    Replace the detections of each filled column with whole-cell ones.

    Arguments:
        units: The units the detections were found in. Those with no ``cells``
            are not columns and nothing here applies to them.
        detections: What the detector found, with its spans final.

    Returns:
        The detections to review, ordered by unit then position. A column that
        is mostly personal data contributes one detection per non-empty cell,
        all of one type; every other unit contributes what it already had.
    """
    detections = list(detections)
    found: dict[str, list[Detection]] = {}
    for item in detections:
        found.setdefault(item.unit_id, []).append(item)

    typed: dict[str, list[Detection]] = {}
    for unit in units:
        if not unit.cells:
            continue
        whole = _whole_column(unit, found.get(unit.id, ()))
        if whole is not None:
            typed[unit.id] = whole

    kept = [item for item in detections if item.unit_id not in typed]
    for cells in typed.values():
        kept.extend(cells)
    return sorted(kept, key=lambda item: (item.unit_id, item.start))


def _whole_column(
    unit: TextUnit, inside: Iterable[Detection]
) -> list[Detection] | None:
    """
    One detection per non-empty cell, or None if this is not that kind of
    column — the cells are prose, or too few of them hold anything.

    The detections of a column that qualifies are dropped in favour of these.
    That includes any that spanned two cells: both cells are replaced entirely,
    so what it covered goes with them, and two edits over one cell would
    overlap and stop the write.
    """
    cells = [(start, end) for start, end in unit.cells if unit.text[start:end].strip()]
    if not cells:
        return None

    covered: dict[str, int] = {}
    reached = 0
    length = 0
    for start, end in cells:
        held = [item for item in inside if start <= item.start and item.end <= end]
        if not held:
            continue
        reached += 1
        length += len(unit.text[start:end].strip())
        for item in held:
            size = item.end - item.start
            covered[item.entity_type] = covered.get(item.entity_type, 0) + size

    if not length or reached < len(cells) * _REACH:
        return None
    if sum(covered.values()) < length * _FILL:
        return None

    # The type that covers the most characters, so one cell read as a place
    # does not retype a column of names. The type name breaks a tie, so the
    # same column always comes back the same way.
    entity_type = max(covered, key=lambda name: (covered[name], name))
    return [_cell(unit, start, end, entity_type) for start, end in cells]


def _cell(unit: TextUnit, start: int, end: int, entity_type: str) -> Detection:
    """
    A whole cell as one detection, without the spaces around it.

    The score is 1.0 because this claim is ours and not the detector's: the
    evidence is the column, not the characters. ``likely`` is true for the same
    reason — a one-word cell is the shape the model gets wrong in prose, which
    is why those are ranked low, but in a column it is the ordinary case. And
    the cell is its own excerpt: its context is the column's name, which the
    review screen already shows beside the row, not the cell above it.
    """
    text = unit.text[start:end]
    start += len(text) - len(text.lstrip())
    end -= len(text) - len(text.rstrip())
    value = unit.text[start:end]
    return Detection(
        unit.id, start, end, entity_type, 1.0, value, excerpt=value, column=True
    )
