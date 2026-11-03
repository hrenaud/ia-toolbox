---
"ia-toolbox": patch
---

fix(anonymization): read names one line at a time

A name in the middle of a document went unreported, so it stayed in the
anonymized copy. `Sophie Marchand`, named in a paragraph between two headings,
was never offered for replacement, and `Thomas Nguyen` was offered for the line
that listed him but not for the table cell that named him again.

The cause was the text handed to the model. A unit's text is not prose: an
adapter joins a heading, a paragraph and a table row with newlines, and none of
them ends in a full stop, so the whole unit reads as one run-on sentence. A
small model given that loses names inside it and takes the headings for people.

The model now reads one line at a time; the patterns keep the whole unit, since
a NIR is accepted on the strength of the words introducing it and those can sit
a line away. On the sample meeting report both missing names are now found and
the false positives `Lieu`, `Participants`, `Décisions` and `Points` are gone —
32 spans over 24 rows, 2 of them doubtful, against 34 over 27 with 6 doubtful.

The README now also states that dates are not detected in French: the French
model has no date category, so a date is left in the copy even though the type
menu offers one.
