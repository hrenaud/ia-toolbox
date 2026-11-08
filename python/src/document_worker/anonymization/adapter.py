"""
The shape every format adapter has.

An adapter does two things: hand out the strings to analyze, and write a copy
with replacements in place. Everything between those two calls — detection,
review, the choice of operator — is the same for every format, which is why
this base class is where the file is read twice rather than held open across
the user's review. A document the user is reviewing may be edited or moved
meanwhile; reading it again at write time is how that is noticed instead of
silently writing a stale copy.
"""

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from document_worker.anonymization.model import Edit, Extraction, TextUnit
from document_worker.anonymization.textmap import TextMap


class MappedUnit:
    """A unit's text map, plus what the review screen shows about it."""

    def __init__(
        self,
        unit_id: str,
        text_map: TextMap,
        location: str,
        context: tuple[str, ...] = (),
        rewritable: bool = True,
        cells: tuple[tuple[int, int], ...] = (),
    ):
        self.id = unit_id
        self.text_map = text_map
        self.location = location
        self.context = context
        self.rewritable = rewritable
        self.cells = cells


class DocumentAdapter:
    """Base class turning a loaded document into units and back again."""

    def extract(self, path: Path) -> Extraction:
        """Read the document and return the strings to analyze."""
        document = self._load(Path(path))
        return Extraction(
            units=[
                TextUnit(
                    unit.id,
                    unit.text_map.text,
                    unit.location,
                    unit.context,
                    unit.rewritable,
                    unit.cells,
                )
                for unit in document.units
            ],
            notes=document.notes,
        )

    def apply(self, path: Path, edits: Iterable[Edit], output_path: Path) -> None:
        """
        Write a copy of the document with ``edits`` applied.

        Arguments:
            path: The original document, read again here.
            edits: Replacements in the offset space of the units ``extract``
                returned for this same document.
            output_path: Where the copy goes. Never the original.

        Raises:
            ValueError: An edit names a unit this document does not have, or
                its offsets do not fit the unit's text. Either means the edits
                were computed against different content, so nothing is written.
        """
        document = self._load(Path(path))
        units = {unit.id: unit for unit in document.units}

        grouped: dict[str, list[Edit]] = {}
        for edit in edits:
            grouped.setdefault(edit.unit_id, []).append(edit)

        unknown = sorted(set(grouped) - set(units))
        if unknown:
            raise ValueError("Edits name units this document does not contain.")

        not_rewritable = sorted(name for name in grouped if not units[name].rewritable)
        if not_rewritable:
            raise ValueError("Edits target text this format does not rewrite.")

        replacements: dict[Any, str] = {}
        for unit_id, unit_edits in grouped.items():
            replacements.update(units[unit_id].text_map.plan(unit_edits))

        self._write(document, replacements, Path(output_path))

    def _load(self, path: Path):
        raise NotImplementedError

    def _write(self, document, replacements: dict[Any, str], output_path: Path) -> None:
        raise NotImplementedError
