---
"ia-toolbox": minor
---

feat(anonymization): type a column of a CSV file as a whole

A column of a table is not prose: every cell in it holds the same kind of
value, which is a stronger claim than anything a detector can make about one
cell on its own. So a column whose cells are mostly personal data now gets one
type, and every one of its cells is replaced.

That closes a leak. The model found names in six cells of a column and missed
the seventh; the seventh name stayed in the anonymized copy and was never
offered for review, and nobody can untick a row that was never shown. And it
makes the review usable on a table: the column is a single row, named after its
header and showing its first values, whose menu retypes every cell at once. On
the sample membership directory, 52 spans become 12 questions instead of ~40.

Two measurements decide a column and both are required. Fill is how much of a
cell its detections cover, averaged only over the cells where something was
found — so it never measures recall, which is the case that has to be accepted.
Reach is how many non-empty cells hold anything at all. Fill alone accepts a
column of reference codes with one name in it; reach alone accepts a column of
free-text comments that each mention somebody. Both thresholds were measured on
a real file and sit in the middle of the gap.

CSV and TSV only. Columns inside an Excel workbook are not typed this way: its
text lives in a shared string table with no notion of a grid, so recognizing a
column there is a separate piece of work.
