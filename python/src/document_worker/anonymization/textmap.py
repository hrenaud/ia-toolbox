"""
The map between a document's text and the fragments that store it.

Shared by every adapter whose text is not a single string: OOXML runs, HTML
inline markup. A detector needs one continuous string; the writer needs to put
a replacement back where the text actually lives. This module owns both
directions, and nothing in it knows anything about XML.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from document_worker.anonymization.model import Edit


@dataclass(frozen=True)
class _Segment:
    """One fragment of the concatenated text.

    A key of None marks a separator: part of the string the detector sees, so
    that the end of one paragraph does not fuse with the start of the next, but
    not a place anything can be written back to.
    """

    key: Any
    text: str
    start: int

    @property
    def end(self) -> int:
        return self.start + len(self.text)


class TextMap:
    """A document unit's text, plus the way back to where it is stored."""

    def __init__(self, segments: Sequence[_Segment], text: str):
        self._segments = segments
        self.text = text

    @classmethod
    def build(cls, pieces: Iterable[tuple[Any, str]]) -> "TextMap":
        """
        Build a map over fragments given in document order.

        No separator is inserted between fragments: one extra character shifts
        every offset after it, which is how a replacement lands on the wrong
        word. An adapter that needs a boundary — a paragraph, a cell, a slide —
        passes it as a piece with a key of None.

        Arguments:
            pieces: (key, text) in document order. The key is opaque here and
                is whatever the adapter needs to write that fragment back.

        Returns:
            The map, with ``text`` the concatenation of every piece.
        """
        segments: list[_Segment] = []
        offset = 0
        for key, text in pieces:
            segments.append(_Segment(key, text, offset))
            offset += len(text)
        return cls(segments, "".join(segment.text for segment in segments))

    def plan(self, edits: Iterable[Edit]) -> dict[Any, str]:
        """
        Turn edits in this unit's offset space into new text per fragment.

        A span inside one fragment is a substring edit. A span across several
        writes the whole replacement into the fragment where it starts and
        empties the covered text from the others, so the replacement inherits
        the formatting of the run the entity starts in — the only choice that
        does not invent formatting. Separators are left alone.

        Edits are applied from the highest offset down, so the offsets of
        earlier edits stay valid while lengths change.

        Arguments:
            edits: Replacements to apply. Order does not matter.

        Returns:
            New text for each fragment key that changed. Untouched fragments
            are absent.

        Raises:
            ValueError: An offset outside the text, an empty or reversed span,
                two overlapping edits, or a span with nothing writable in it.
                A bad offset must stop the write rather than silently corrupt
                the document.
        """
        ordered = sorted(edits, key=lambda edit: (edit.start, edit.end))
        self._reject_bad_spans(ordered)

        # Start from each fragment's current text and rewrite in place, from the
        # last edit to the first.
        pending: dict[int, str] = {}
        for edit in reversed(ordered):
            covered = self._resolve(edit.start, edit.end)
            if not covered:
                raise ValueError("No writable text in the edit span.")
            first, *rest = covered
            index, local_start, local_end = first
            pending[index] = self._rewrite(
                pending, index, local_start, local_end, edit.replacement
            )
            for index, local_start, local_end in rest:
                pending[index] = self._rewrite(
                    pending, index, local_start, local_end, ""
                )

        return {self._segments[index].key: text for index, text in pending.items()}

    def _rewrite(
        self,
        pending: dict[int, str],
        index: int,
        start: int,
        end: int,
        replacement: str,
    ) -> str:
        current = pending.get(index, self._segments[index].text)
        return current[:start] + replacement + current[end:]

    def _resolve(self, start: int, end: int) -> list[tuple[int, int, int]]:
        """Return the writable fragments a span covers, as (index, from, to)."""
        covered = []
        for index, segment in enumerate(self._segments):
            if segment.key is None or segment.end <= start or segment.start >= end:
                continue
            local_start = max(start, segment.start) - segment.start
            local_end = min(end, segment.end) - segment.start
            covered.append((index, local_start, local_end))
        return covered

    def _reject_bad_spans(self, ordered: Sequence[Edit]) -> None:
        previous_end = 0
        for edit in ordered:
            if edit.start < 0 or edit.end > len(self.text):
                raise ValueError("Edit offsets fall outside the unit's text.")
            if edit.start >= edit.end:
                raise ValueError("An edit must cover at least one character.")
            if edit.start < previous_end:
                raise ValueError("Edits overlap.")
            previous_end = edit.end
