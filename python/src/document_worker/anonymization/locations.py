"""
The codes that say where a unit is.

Every other string an adapter emits is a code the interface translates, and a
location is no different: it is shown beside each detection on the review
screen, where an English sentence written here would be an English sentence a
French user reads.

The grammar is one code, optionally followed by ``:`` and the single variable
part — a part number, a column name. Anything richer would need a parser on the
other side of the protocol for no gain.

The interface mirrors this list in ``src/features/anonymization/locationLabels.ts``
and its test fails when a code has no French and English string.
"""

LOCATION_CODES = (
    # The whole file is one string: text, Markdown, JSON, HTML, XML.
    "document",
    # Tabular and line-delimited files, which have one unit per column or line.
    "column",
    "column_number",
    "line",
    # Word
    "document_body",
    "header",
    "footer",
    "footnotes",
    "endnotes",
    "comments",
    # PowerPoint
    "slide",
    "slide_notes",
    "slide_layout",
    "slide_master",
    "notes_master",
    "slide_comments",
    # Excel
    "cell_values",
    "sheet",
    "cell_comments",
    # Read and reported, never rewritten.
    "sheet_formulas",
    "sheet_names",
)
